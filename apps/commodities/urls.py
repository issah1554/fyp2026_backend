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
    path("categories/", CommodityCategoryListCreateView.as_view(), name="category-list"),
    path("categories/<str:category_id>/", CommodityCategoryDetailView.as_view(), name="category-detail"),
    path("units/", CommodityUnitListCreateView.as_view(), name="unit-list"),
    path("units/<str:unit_id>/", CommodityUnitDetailView.as_view(), name="unit-detail"),
    path("", CommodityListCreateView.as_view(), name="commodity-list"),
    path("<str:commodity_id>/", CommodityDetailView.as_view(), name="commodity-detail"),
]
