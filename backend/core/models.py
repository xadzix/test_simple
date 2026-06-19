from pathlib import Path
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.db import models
from pgvector.django import VectorField


def validate_excel_file(value):
    extension = Path(value.name).suffix.lower()
    if extension not in {".xlsx", ".xls"}:
        raise ValidationError("Поддерживаются только файлы .xlsx и .xls")
    if value.size > 20 * 1024 * 1024:
        raise ValidationError("Размер файла не должен превышать 20 МБ")


def upload_path(instance, filename):
    extension = Path(filename).suffix.lower()
    kind = "price_lists" if isinstance(instance, PriceList) else "estimates"
    return f"{kind}/{uuid4().hex}{extension}"


class CreatedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True


class Supplier(CreatedModel):
    class Currency(models.TextChoices):
        RUB = "RUB", "Российский рубль"
        USD = "USD", "Доллар США"
        EUR = "EUR", "Евро"
        CNY = "CNY", "Китайский юань"

    name = models.CharField("Название", max_length=255)
    inn = models.CharField("ИНН", max_length=12, unique=True)
    currency = models.CharField(
        "Валюта", max_length=3, choices=Currency.choices, default=Currency.RUB
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class ImportStatus(models.TextChoices):
    UPLOADED = "uploaded", "Файл загружен"
    PROCESSING = "processing", "Обработка"
    COMPLETED = "completed", "Готово"
    FAILED = "failed", "Ошибка"


class ImportModel(CreatedModel):
    original_name = models.CharField(max_length=255)
    file = models.FileField(
        upload_to=upload_path, validators=[validate_excel_file]
    )
    sheet_name = models.CharField(max_length=255, blank=True)
    header_row = models.PositiveIntegerField(default=1)
    column_mapping = models.JSONField(default=dict, blank=True)
    status = models.CharField(
        max_length=16,
        choices=ImportStatus.choices,
        default=ImportStatus.UPLOADED,
    )
    progress = models.PositiveSmallIntegerField(default=0)
    rows_total = models.PositiveIntegerField(default=0)
    rows_processed = models.PositiveIntegerField(default=0)
    error_message = models.TextField(blank=True)

    class Meta:
        abstract = True


class CatalogProduct(CreatedModel):
    sku = models.CharField("Артикул", max_length=255, unique=True)
    name = models.CharField("Наименование", max_length=500)
    unit = models.CharField("Ед. изм.", max_length=50, blank=True)
    group = models.CharField("Группа", max_length=255, blank=True)
    embedding = VectorField(dimensions=1536, null=True)

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["name"]),
            models.Index(fields=["group"]),
        ]

    def __str__(self):
        return f"{self.sku} — {self.name}"


class PriceList(ImportModel):
    supplier = models.ForeignKey(
        Supplier, related_name="price_lists", on_delete=models.CASCADE
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.supplier}: {self.original_name}"


class SupplierPriceItem(models.Model):
    price_list = models.ForeignKey(
        PriceList, related_name="items", on_delete=models.CASCADE
    )
    catalog_product = models.ForeignKey(
        CatalogProduct,
        related_name="supplier_items",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    row_number = models.PositiveIntegerField()
    sku = models.CharField(max_length=255, blank=True)
    name = models.CharField(max_length=500)
    unit = models.CharField(max_length=50, blank=True)
    price = models.DecimalField(
        max_digits=16, decimal_places=2, null=True, blank=True
    )

    class Meta:
        ordering = ["row_number"]
        indexes = [models.Index(fields=["sku"]), models.Index(fields=["name"])]


class Project(CreatedModel):
    name = models.CharField(max_length=255)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name


class Estimate(ImportModel):
    project = models.ForeignKey(
        Project, related_name="estimates", on_delete=models.CASCADE
    )
    name = models.CharField(max_length=255)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.project}: {self.name}"


class EstimateItem(models.Model):
    class MatchStatus(models.TextChoices):
        MATCHED = "matched", "Сопоставлено"
        NO_MATCH = "no_match", "Без соответствия"

    estimate = models.ForeignKey(
        Estimate, related_name="items", on_delete=models.CASCADE
    )
    catalog_product = models.ForeignKey(
        CatalogProduct,
        related_name="estimate_items",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    row_number = models.PositiveIntegerField()
    sku = models.CharField(max_length=255, blank=True)
    name = models.CharField(max_length=500)
    unit = models.CharField(max_length=50, blank=True)
    quantity = models.DecimalField(
        max_digits=16, decimal_places=3, null=True, blank=True
    )
    material_price = models.DecimalField(
        max_digits=16, decimal_places=2, null=True, blank=True
    )
    installation_price = models.DecimalField(
        max_digits=16, decimal_places=2, null=True, blank=True
    )
    match_status = models.CharField(
        max_length=16,
        choices=MatchStatus.choices,
        default=MatchStatus.NO_MATCH,
    )
    match_confidence = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    match_explanation = models.CharField(max_length=500, blank=True)

    class Meta:
        ordering = ["row_number"]
        indexes = [
            models.Index(fields=["match_status"]),
            models.Index(fields=["sku"]),
        ]

    @property
    def total(self):
        quantity = self.quantity or 0
        return quantity * (
            (self.material_price or 0) + (self.installation_price or 0)
        )
