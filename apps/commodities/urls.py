from django.urls import path

from .views import (
    CommodityCategoryDetailView,
    CommodityCategoryListCreateView,
    CommodityDetailView,
    CommodityListCreateView,
    CommodityUnitDetailView,
    CommodityUnitListCreateView,
)

app_name = "commodities"

urlpatterns = [
    path("commodities/categories", CommodityCategoryListCreateView.as_view(), name="category-list"),
    path("commodities/categories/<str:category_id>", CommodityCategoryDetailView.as_view(), name="category-detail"),
    path("commodities/units", CommodityUnitListCreateView.as_view(), name="unit-list"),
    path("commodities/units/<str:unit_id>", CommodityUnitDetailView.as_view(), name="unit-detail"),
    path("commodities", CommodityListCreateView.as_view(), name="commodity-list"),
    path("commodities/<str:commodity_id>", CommodityDetailView.as_view(), name="commodity-detail"),
]
