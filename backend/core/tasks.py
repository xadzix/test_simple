from celery import shared_task
from django.db import transaction

from .excel import decimal_at, iter_data_rows, value_at
from .matcher import ProductMatcher
from .models import (
    CatalogProduct,
    Estimate,
    EstimateItem,
    ImportStatus,
    PriceList,
    SupplierPriceItem,
)


def _set_failed(instance, error):
    instance.status = ImportStatus.FAILED
    instance.error_message = str(error)[:4000]
    instance.save(update_fields=["status", "error_message"])


def _progress(instance, processed, total):
    progress = min(99, int(processed / max(total, 1) * 100))
    type(instance).objects.filter(pk=instance.pk).update(
        rows_processed=processed, progress=progress
    )


@shared_task
def parse_price_list(price_list_id):
    price_list = PriceList.objects.get(pk=price_list_id)
    try:
        price_list.status = ImportStatus.PROCESSING
        price_list.progress = 1
        price_list.error_message = ""
        price_list.save(update_fields=["status", "progress", "error_message"])

        rows = list(
            iter_data_rows(
                price_list.file.path,
                price_list.sheet_name,
                price_list.header_row,
            )
        )
        price_list.rows_total = len(rows)
        price_list.save(update_fields=["rows_total"])
        products_by_sku = {
            p.sku.strip().lower(): p
            for p in CatalogProduct.objects.exclude(sku="")
        }

        with transaction.atomic():
            price_list.items.all().delete()
            batch = []
            for processed, (row_number, row) in enumerate(rows, start=1):
                sku = value_at(row, price_list.column_mapping, "sku")
                name = value_at(row, price_list.column_mapping, "name")
                if not name and not sku:
                    continue
                batch.append(
                    SupplierPriceItem(
                        price_list=price_list,
                        catalog_product=products_by_sku.get(sku.lower()),
                        row_number=row_number,
                        sku=sku,
                        name=name or sku,
                        unit=value_at(row, price_list.column_mapping, "unit"),
                        price=decimal_at(
                            row, price_list.column_mapping, "price"
                        ),
                    )
                )
                if len(batch) >= 500:
                    SupplierPriceItem.objects.bulk_create(batch)
                    batch = []
                if processed % 100 == 0:
                    _progress(price_list, processed, len(rows))
            if batch:
                SupplierPriceItem.objects.bulk_create(batch)

        price_list.status = ImportStatus.COMPLETED
        price_list.progress = 100
        price_list.rows_processed = len(rows)
        price_list.save(
            update_fields=[
                "status",
                "progress",
                "rows_processed",
            ]
        )
        return {"created": price_list.items.count()}
    except Exception as exc:
        _set_failed(price_list, exc)
        raise


@shared_task
def parse_estimate(estimate_id):
    estimate = Estimate.objects.get(pk=estimate_id)
    try:
        estimate.status = ImportStatus.PROCESSING
        estimate.progress = 1
        estimate.error_message = ""
        estimate.save(update_fields=["status", "progress", "error_message"])

        rows = list(
            iter_data_rows(
                estimate.file.path, estimate.sheet_name, estimate.header_row
            )
        )
        estimate.rows_total = len(rows)
        estimate.save(update_fields=["rows_total"])
        matcher = ProductMatcher(CatalogProduct.objects.all())

        parsed = []
        for processed, (row_number, row) in enumerate(rows, start=1):
            sku = value_at(row, estimate.column_mapping, "sku")
            name = value_at(row, estimate.column_mapping, "name")
            if not name and not sku:
                continue
            parsed.append(
                {
                    "row_number": row_number,
                    "sku": sku,
                    "name": name or sku,
                    "unit": value_at(row, estimate.column_mapping, "unit"),
                    "quantity": decimal_at(
                        row, estimate.column_mapping, "quantity"
                    ),
                    "material_price": decimal_at(
                        row, estimate.column_mapping, "material_price"
                    ),
                    "installation_price": decimal_at(
                        row, estimate.column_mapping, "installation_price"
                    ),
                }
            )
            if processed % 100 == 0:
                _progress(estimate, processed, len(rows))

        matches = matcher.match_many(
            [(item["sku"], item["name"], item["unit"]) for item in parsed]
        )
        with transaction.atomic():
            estimate.items.all().delete()
            EstimateItem.objects.bulk_create(
                [
                    EstimateItem(
                        estimate=estimate,
                        catalog_product=match.product,
                        **item,
                        match_status=(
                            EstimateItem.MatchStatus.MATCHED
                            if match.product
                            else EstimateItem.MatchStatus.NO_MATCH
                        ),
                        match_confidence=match.confidence,
                        match_explanation=match.explanation,
                    )
                    for item, match in zip(parsed, matches, strict=True)
                ],
                batch_size=500,
            )

        estimate.status = ImportStatus.COMPLETED
        estimate.progress = 100
        estimate.rows_processed = len(rows)
        estimate.save(
            update_fields=[
                "status",
                "progress",
                "rows_processed",
            ]
        )
        return {"created": estimate.items.count()}
    except Exception as exc:
        _set_failed(estimate, exc)
        raise


@shared_task
def rematch_estimate(estimate_id):
    estimate = Estimate.objects.get(pk=estimate_id)
    matcher = ProductMatcher(CatalogProduct.objects.all())
    items = list(estimate.items.all())
    matches = matcher.match_many(
        [(item.sku, item.name, item.unit) for item in items]
    )
    for item, match in zip(items, matches, strict=True):
        item.catalog_product = match.product
        item.match_status = (
            EstimateItem.MatchStatus.MATCHED
            if match.product
            else EstimateItem.MatchStatus.NO_MATCH
        )
        item.match_confidence = match.confidence
        item.match_explanation = match.explanation
    EstimateItem.objects.bulk_update(
        items,
        [
            "catalog_product",
            "match_status",
            "match_confidence",
            "match_explanation",
        ],
    )
    return {"processed": len(items)}
