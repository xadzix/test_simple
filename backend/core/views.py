from django.db.models import Count, Q
from django.http import JsonResponse
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from .excel import read_preview
from .models import (
    CatalogProduct,
    Estimate,
    EstimateItem,
    PriceList,
    Project,
    Supplier,
    SupplierPriceItem,
)
from .serializers import (
    CatalogProductSerializer,
    EstimateItemSerializer,
    EstimateSerializer,
    PriceListSerializer,
    ProjectSerializer,
    SupplierPriceItemSerializer,
    SupplierSerializer,
)
from .tasks import parse_estimate, parse_price_list, rematch_estimate


def health(request):
    return JsonResponse({"status": "ok"})


class SupplierViewSet(viewsets.ModelViewSet):
    serializer_class = SupplierSerializer
    search_fields = ["name", "inn"]

    def get_queryset(self):
        return Supplier.objects.annotate(
            price_lists_count=Count("price_lists")
        ).order_by("name")


class CatalogProductViewSet(viewsets.ModelViewSet):
    serializer_class = CatalogProductSerializer
    search_fields = ["sku", "name", "group"]

    def get_queryset(self):
        return CatalogProduct.objects.annotate(
            supplier_offers_count=Count("supplier_items")
        ).order_by("name")


class PreviewAndParseMixin:
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    required_mapping = []
    parse_task = None

    @action(detail=True, methods=["get"])
    def preview(self, request, pk=None):
        instance = self.get_object()
        try:
            header_row = max(1, int(request.query_params.get("header_row", 1)))
            data = read_preview(
                instance.file.path,
                request.query_params.get("sheet_name") or None,
                header_row,
            )
            return Response(data)
        except Exception as exc:
            raise ValidationError(
                {"detail": f"Не удалось прочитать Excel: {exc}"}
            ) from exc

    def validate_parse_request(self, request):
        mapping = request.data.get("column_mapping") or {}
        missing = [
            field
            for field in self.required_mapping
            if mapping.get(field) in (None, "")
        ]
        if missing:
            raise ValidationError(
                {
                    "column_mapping": f"Не выбраны обязательные поля: {', '.join(missing)}"
                }
            )
        try:
            header_row = max(1, int(request.data.get("header_row", 1)))
        except (TypeError, ValueError) as exc:
            raise ValidationError(
                {"header_row": "Некорректный номер строки"}
            ) from exc
        return {
            "column_mapping": mapping,
            "header_row": header_row,
            "sheet_name": request.data.get("sheet_name", ""),
        }

    @action(detail=True, methods=["post"])
    def parse(self, request, pk=None):
        instance = self.get_object()
        payload = self.validate_parse_request(request)
        for key, value in payload.items():
            setattr(instance, key, value)
        instance.status = "uploaded"
        instance.progress = 0
        instance.error_message = ""
        instance.save()
        self.parse_task.delay(instance.pk)
        return Response(
            self.get_serializer(instance).data, status=status.HTTP_202_ACCEPTED
        )


class PriceListViewSet(PreviewAndParseMixin, viewsets.ModelViewSet):
    serializer_class = PriceListSerializer
    required_mapping = ["name", "price"]
    parse_task = parse_price_list
    filterset_fields = ["supplier"]

    def get_queryset(self):
        return PriceList.objects.select_related("supplier").annotate(
            items_count=Count("items")
        )


class SupplierPriceItemViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = SupplierPriceItemSerializer
    filterset_fields = ["price_list"]

    def get_queryset(self):
        return SupplierPriceItem.objects.select_related(
            "catalog_product", "price_list"
        )


class ProjectViewSet(viewsets.ModelViewSet):
    serializer_class = ProjectSerializer

    def get_queryset(self):
        return Project.objects.annotate(
            estimates_count=Count("estimates")
        ).order_by("-created_at")


class EstimateViewSet(PreviewAndParseMixin, viewsets.ModelViewSet):
    serializer_class = EstimateSerializer
    required_mapping = ["name", "quantity"]
    parse_task = parse_estimate
    filterset_fields = ["project"]

    def get_queryset(self):
        return (
            Estimate.objects.select_related("project")
            .prefetch_related("items")
            .annotate(
                items_count=Count("items", distinct=True),
                matched_count=Count(
                    "items",
                    filter=Q(items__match_status="matched"),
                    distinct=True,
                ),
                unmatched_count=Count(
                    "items",
                    filter=Q(items__match_status="no_match"),
                    distinct=True,
                ),
            )
        )

    @action(detail=True, methods=["post"])
    def auto_match(self, request, pk=None):
        instance = self.get_object()
        rematch_estimate.delay(instance.pk)
        return Response(
            {"detail": "Сопоставление запущено"},
            status=status.HTTP_202_ACCEPTED,
        )


class EstimateItemViewSet(
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = EstimateItemSerializer
    filterset_fields = ["estimate", "match_status"]
    search_fields = [
        "sku",
        "name",
        "catalog_product__name",
        "catalog_product__sku",
    ]

    def get_queryset(self):
        return EstimateItem.objects.select_related(
            "catalog_product", "estimate"
        )
