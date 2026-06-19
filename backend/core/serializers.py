from decimal import Decimal

from rest_framework import serializers

from .models import (
    CatalogProduct,
    Estimate,
    EstimateItem,
    PriceList,
    Project,
    Supplier,
    SupplierPriceItem,
)


class SupplierSerializer(serializers.ModelSerializer):
    price_lists_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = Supplier
        fields = [
            "id",
            "name",
            "inn",
            "currency",
            "price_lists_count",
            "created_at",
        ]
        read_only_fields = ["created_at"]

    def validate_inn(self, value):
        value = value.strip()
        if not value.isdigit() or len(value) not in (10, 12):
            raise serializers.ValidationError(
                "ИНН должен содержать 10 или 12 цифр"
            )
        return value


class CatalogProductSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = CatalogProduct
        fields = ["id", "sku", "name", "unit", "group"]


class CatalogProductSerializer(serializers.ModelSerializer):
    supplier_offers_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = CatalogProduct
        fields = [
            "id",
            "sku",
            "name",
            "unit",
            "group",
            "supplier_offers_count",
            "created_at",
        ]
        read_only_fields = ["created_at"]

    def update(self, instance, validated_data):
        if {"name", "unit", "group"} & validated_data.keys():
            validated_data["embedding"] = None
        return super().update(instance, validated_data)


class PriceListSerializer(serializers.ModelSerializer):
    supplier_name = serializers.CharField(
        source="supplier.name", read_only=True
    )
    items_count = serializers.IntegerField(read_only=True, default=0)
    file = serializers.FileField(write_only=True)

    class Meta:
        model = PriceList
        fields = [
            "id",
            "supplier",
            "supplier_name",
            "original_name",
            "file",
            "sheet_name",
            "header_row",
            "column_mapping",
            "status",
            "progress",
            "rows_total",
            "rows_processed",
            "items_count",
            "error_message",
            "created_at",
        ]
        read_only_fields = [
            "original_name",
            "sheet_name",
            "header_row",
            "column_mapping",
            "status",
            "progress",
            "rows_total",
            "rows_processed",
            "error_message",
            "created_at",
        ]

    def create(self, validated_data):
        uploaded_file = validated_data["file"]
        validated_data["original_name"] = uploaded_file.name
        return super().create(validated_data)


class SupplierPriceItemSerializer(serializers.ModelSerializer):
    catalog_product_detail = CatalogProductSummarySerializer(
        source="catalog_product", read_only=True
    )

    class Meta:
        model = SupplierPriceItem
        fields = [
            "id",
            "price_list",
            "row_number",
            "sku",
            "name",
            "unit",
            "price",
            "catalog_product",
            "catalog_product_detail",
        ]


class ProjectSerializer(serializers.ModelSerializer):
    estimates_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = Project
        fields = [
            "id",
            "name",
            "estimates_count",
            "created_at",
        ]
        read_only_fields = ["created_at"]


class EstimateSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source="project.name", read_only=True)
    items_count = serializers.IntegerField(read_only=True, default=0)
    matched_count = serializers.IntegerField(read_only=True, default=0)
    unmatched_count = serializers.IntegerField(read_only=True, default=0)
    total_amount = serializers.SerializerMethodField()
    file = serializers.FileField(write_only=True)

    class Meta:
        model = Estimate
        fields = [
            "id",
            "project",
            "project_name",
            "name",
            "original_name",
            "file",
            "sheet_name",
            "header_row",
            "column_mapping",
            "status",
            "progress",
            "rows_total",
            "rows_processed",
            "items_count",
            "matched_count",
            "unmatched_count",
            "total_amount",
            "error_message",
            "created_at",
        ]
        read_only_fields = [
            "original_name",
            "sheet_name",
            "header_row",
            "column_mapping",
            "status",
            "progress",
            "rows_total",
            "rows_processed",
            "error_message",
            "created_at",
        ]

    def create(self, validated_data):
        uploaded_file = validated_data["file"]
        validated_data["original_name"] = uploaded_file.name
        return super().create(validated_data)

    def get_total_amount(self, obj):
        total = Decimal("0")
        for item in obj.items.all():
            total += item.total
        return total


class EstimateItemSerializer(serializers.ModelSerializer):
    catalog_product_detail = CatalogProductSummarySerializer(
        source="catalog_product", read_only=True
    )
    total = serializers.DecimalField(
        max_digits=18, decimal_places=2, read_only=True
    )

    class Meta:
        model = EstimateItem
        fields = [
            "id",
            "estimate",
            "row_number",
            "sku",
            "name",
            "unit",
            "quantity",
            "material_price",
            "installation_price",
            "total",
            "catalog_product",
            "catalog_product_detail",
            "match_status",
            "match_confidence",
            "match_explanation",
        ]
        read_only_fields = [
            "estimate",
            "row_number",
            "sku",
            "name",
            "unit",
            "quantity",
            "material_price",
            "installation_price",
            "match_confidence",
            "match_explanation",
        ]

    def validate(self, attrs):
        product = attrs.get(
            "catalog_product", getattr(self.instance, "catalog_product", None)
        )
        status = attrs.get(
            "match_status", getattr(self.instance, "match_status", None)
        )
        if status == EstimateItem.MatchStatus.MATCHED and not product:
            raise serializers.ValidationError(
                "Для статуса «Сопоставлено» выберите товар"
            )
        return attrs

    def update(self, instance, validated_data):
        if (
            validated_data.get("match_status")
            == EstimateItem.MatchStatus.NO_MATCH
        ):
            validated_data["catalog_product"] = None
        elif validated_data.get("catalog_product"):
            validated_data["match_status"] = EstimateItem.MatchStatus.MATCHED
        instance = super().update(instance, validated_data)
        instance.match_confidence = (
            Decimal("100") if instance.catalog_product else Decimal("0")
        )
        instance.match_explanation = (
            "Выбрано пользователем"
            if instance.catalog_product
            else "Явно отмечено без соответствия"
        )
        instance.save(
            update_fields=[
                "match_confidence",
                "match_explanation",
            ]
        )
        return instance
