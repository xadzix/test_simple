from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    CatalogProductViewSet,
    EstimateItemViewSet,
    EstimateViewSet,
    PriceListViewSet,
    ProjectViewSet,
    SupplierPriceItemViewSet,
    SupplierViewSet,
    health,
)

router = DefaultRouter()
router.register("suppliers", SupplierViewSet, basename="supplier")
router.register("price-lists", PriceListViewSet, basename="price-list")
router.register(
    "supplier-items", SupplierPriceItemViewSet, basename="supplier-item"
)
router.register("products", CatalogProductViewSet, basename="product")
router.register("projects", ProjectViewSet, basename="project")
router.register("estimates", EstimateViewSet, basename="estimate")
router.register(
    "estimate-items", EstimateItemViewSet, basename="estimate-item"
)

urlpatterns = [path("health/", health), path("", include(router.urls))]
