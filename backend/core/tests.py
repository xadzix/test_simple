import os
import tempfile
from decimal import Decimal
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from openpyxl import Workbook
from rest_framework.test import APITestCase

from .excel import read_preview
from .matcher import ProductMatcher
from .models import CatalogProduct, PriceList, Supplier
from .tasks import parse_price_list


class SupplierApiTests(APITestCase):
    def test_supplier_crud_and_search(self):
        created = self.client.post(
            "/api/suppliers/",
            {
                "name": "Тестовый поставщик",
                "inn": "7701234567",
                "currency": "RUB",
            },
            format="json",
        )
        self.assertEqual(created.status_code, 201)
        response = self.client.get("/api/suppliers/?search=7701")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)

    def test_invalid_inn_is_rejected(self):
        response = self.client.post(
            "/api/suppliers/",
            {"name": "Ошибка", "inn": "123", "currency": "RUB"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)


class CatalogProductApiTests(APITestCase):
    def test_edit_clears_embedding(self):
        product = CatalogProduct.objects.create(
            sku="A-1",
            name="Старое название",
            embedding=[1.0, *([0.0] * 1535)],
        )
        response = self.client.patch(
            f"/api/products/{product.pk}/",
            {"name": "Новое название"},
            format="json",
        )
        product.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(product.embedding)


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class ImportValidationTests(APITestCase):
    def setUp(self):
        supplier = Supplier.objects.create(name="Поставщик", inn="7701234567")
        self.price_list = PriceList.objects.create(
            supplier=supplier,
            original_name="price.xlsx",
            file=SimpleUploadedFile("price.xlsx", b"test"),
        )

    def test_missing_mapping_is_rejected(self):
        response = self.client.post(
            f"/api/price-lists/{self.price_list.pk}/parse/",
            {"column_mapping": {}},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("column_mapping", response.data)

    def test_invalid_header_row_is_rejected(self):
        response = self.client.post(
            f"/api/price-lists/{self.price_list.pk}/parse/",
            {
                "column_mapping": {"name": 1, "price": 2},
                "header_row": "wrong",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("header_row", response.data)

    def test_preview_error_uses_validation_error(self):
        response = self.client.get(
            f"/api/price-lists/{self.price_list.pk}/preview/?header_row=wrong"
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("detail", response.data)


class ExcelTests(TestCase):
    @staticmethod
    def vector(x=1.0, y=0.0):
        return [x, y, *([0.0] * 1534)]

    def make_xlsx(self):
        handle = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
        handle.close()
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Прайс"
        sheet.append(["Код", "Товар", "Цена", "Ед."])
        sheet.append(["A-1", "Кабель ВВГ 3x2.5", 120.5, "м"])
        workbook.save(handle.name)
        return handle.name

    def test_preview_returns_columns_and_rows(self):
        path = self.make_xlsx()
        try:
            preview = read_preview(path)
            self.assertEqual(preview["columns"][1]["label"], "Товар")
            self.assertEqual(preview["rows"][0][0], "A-1")
        finally:
            os.unlink(path)

    def test_matcher_prefers_exact_sku(self):
        product = CatalogProduct.objects.create(
            sku="A-1", name="Кабель ВВГ", unit="м"
        )
        with patch("core.matcher.create_embeddings") as create:
            result = ProductMatcher([product]).match("A-1", "совсем другое")
        self.assertEqual(result.product, product)
        self.assertEqual(result.confidence, 100)
        create.assert_not_called()

    @patch("core.matcher.create_embeddings")
    def test_matcher_finds_similar_name(self, create):
        product = CatalogProduct.objects.create(
            sku="A-1", name="Кабель ВВГ 3x2.5", unit="м"
        )
        create.side_effect = [[self.vector()], [self.vector()]]
        result = ProductMatcher([product]).match("", "Кабель ВВГ 3x2,5", "м")
        self.assertEqual(result.product, product)

    def test_matcher_does_not_ignore_mismatched_sku(self):
        CatalogProduct.objects.create(sku="511-7975", name="Топливный насос")
        with patch("core.matcher.create_embeddings") as create:
            result = ProductMatcher(CatalogProduct.objects.all()).match(
                "319-0678", "Топливный насос"
            )
        self.assertIsNone(result.product)
        self.assertEqual(result.confidence, 0)
        create.assert_not_called()

    @patch("core.matcher.create_embeddings")
    def test_matcher_rejects_weak_name_similarity(self, create):
        CatalogProduct.objects.create(sku="511-7975", name="Топливный насос")
        create.side_effect = [[self.vector()], [self.vector(0.0, 1.0)]]
        result = ProductMatcher(CatalogProduct.objects.all()).match(
            "", "Шланг топливный"
        )
        self.assertIsNone(result.product)

    @patch("core.matcher.create_embeddings")
    def test_matcher_rejects_ambiguous_candidates(self, create):
        CatalogProduct.objects.create(sku="A-1", name="Насос топливный")
        CatalogProduct.objects.create(sku="A-2", name="Топливный насос")
        create.side_effect = [
            [self.vector(), self.vector(0.995, 0.1)],
            [self.vector()],
        ]
        result = ProductMatcher(CatalogProduct.objects.all()).match(
            "", "Насос топлива"
        )
        self.assertIsNone(result.product)
        self.assertEqual(
            result.explanation, "Найдено несколько похожих товаров"
        )

    @patch("core.matcher.create_embeddings", side_effect=RuntimeError)
    def test_matcher_keeps_item_unmatched_when_openai_is_unavailable(self, _):
        CatalogProduct.objects.create(sku="A-1", name="Топливный насос")
        result = ProductMatcher(CatalogProduct.objects.all()).match(
            "", "Насос топлива"
        )
        self.assertIsNone(result.product)
        self.assertEqual(result.confidence, 0)


class PriceListTaskTests(TestCase):
    @override_settings(MEDIA_ROOT=tempfile.mkdtemp())
    def test_price_list_is_parsed_and_linked(self):
        supplier = Supplier.objects.create(name="Поставщик", inn="7701234567")
        product = CatalogProduct.objects.create(
            sku="A-1", name="Кабель", unit="м"
        )
        handle = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
        handle.close()
        workbook = Workbook()
        sheet = workbook.active
        sheet.append(["Код", "Наименование", "Цена", "Ед."])
        sheet.append(["A-1", "Кабель", 123.45, "м"])
        workbook.save(handle.name)
        with open(handle.name, "rb") as stream:
            price_list = PriceList.objects.create(
                supplier=supplier,
                original_name="price.xlsx",
                file=SimpleUploadedFile("price.xlsx", stream.read()),
                column_mapping={"sku": 0, "name": 1, "price": 2, "unit": 3},
            )
        os.unlink(handle.name)
        parse_price_list.apply(args=[price_list.pk]).get()
        price_list.refresh_from_db()
        item = price_list.items.get()
        self.assertEqual(price_list.status, "completed")
        self.assertEqual(item.catalog_product, product)
        self.assertEqual(item.price, Decimal("123.45"))
