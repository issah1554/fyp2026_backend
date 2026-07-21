from django.urls import path

from .views import (
    CommodityPriceComparisonView,
    CommodityPriceHistoryView,
    CommodityPricesView,
    MarketDetailView,
    MarketLatestPricesView,
    MarketListCreateView,
    MarketNestedPriceListCreateView,
    MarketPriceDetailView,
    MarketPriceListCreateView,
)

app_name = "markets"

urlpatterns = [
    path("markets", MarketListCreateView.as_view(), name="market-list"),
    path("markets/<str:market_id>", MarketDetailView.as_view(), name="market-detail"),
    path("market-prices", MarketPriceListCreateView.as_view(), name="market-price-list"),
    path("market-prices/<str:price_id>", MarketPriceDetailView.as_view(), name="market-price-detail"),
    path("markets/<str:market_id>/prices", MarketNestedPriceListCreateView.as_view(), name="market-nested-price-list"),
    path("markets/<str:market_id>/latest-prices", MarketLatestPricesView.as_view(), name="market-latest-prices"),
    path("commodities/<str:commodity_id>/prices", CommodityPricesView.as_view(), name="commodity-prices"),
    path("commodities/<str:commodity_id>/price-history", CommodityPriceHistoryView.as_view(), name="commodity-price-history"),
    path(
        "commodities/<str:commodity_id>/price-comparison",
        CommodityPriceComparisonView.as_view(),
        name="commodity-price-comparison",
    ),
]
