from django.urls import path

from .views import (
    CommodityCategoryDetailView,
    CommodityCategoryListCreateView,
    CommodityDetailView,
    CommodityListCreateView,
    MarketListView,
    MarketPriceRecordDetailView,
    MarketPriceRecordListCreateView,
)

app_name = "commodities"

urlpatterns = [
    path("categories/", CommodityCategoryListCreateView.as_view(), name="category-list"),
    path("categories/<str:category_id>/", CommodityCategoryDetailView.as_view(), name="category-detail"),
    path("markets/", MarketListView.as_view(), name="market-list"),
    path("market-records/", MarketPriceRecordListCreateView.as_view(), name="market-record-list"),
    path("market-records/<str:record_id>/", MarketPriceRecordDetailView.as_view(), name="market-record-detail"),
    path("", CommodityListCreateView.as_view(), name="commodity-list"),
    path("<str:commodity_id>/", CommodityDetailView.as_view(), name="commodity-detail"),
]
