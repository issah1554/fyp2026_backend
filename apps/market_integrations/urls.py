from django.urls import path

from .views import (
    MarketIntegrationHealthView,
    MarketIntegrationSourceListView,
    MarketIntegrationSyncView,
    MarketIntegrationUpdateCheckView,
    NormalizedMarketPriceListView,
    SourceNormalizedMarketPriceListView,
    StoredMarketPriceListView,
)

app_name = "market_integrations"

urlpatterns = [
    path("market-integrations/sources", MarketIntegrationSourceListView.as_view(), name="source-list"),
    path("market-integrations/health", MarketIntegrationHealthView.as_view(), name="source-health"),
    path("market-integrations/live-prices", NormalizedMarketPriceListView.as_view(), name="normalized-live-price-list"),
    path("market-integrations/prices", StoredMarketPriceListView.as_view(), name="stored-price-list"),
    path("market-integrations/updates", MarketIntegrationUpdateCheckView.as_view(), name="update-check"),
    path("market-integrations/sync", MarketIntegrationSyncView.as_view(), name="sync-prices"),
    path(
        "market-integrations/live-prices/<str:source>",
        SourceNormalizedMarketPriceListView.as_view(),
        name="source-normalized-live-price-list",
    ),
]
