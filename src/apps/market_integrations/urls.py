from django.urls import path

from .views import (
    MarketIntegrationHealthView,
    MarketIntegrationRawImportView,
    MarketIntegrationSourceListView,
    MarketIntegrationStandardizeView,
    MarketIntegrationSyncView,
    MarketIntegrationUpdateCheckView,
    NormalizedMarketPriceListView,
    RawMarketPriceListView,
    SourceNormalizedMarketPriceListView,
    StoredMarketPriceListView,
)

app_name = "market_integrations"

urlpatterns = [
    path("market-integrations/sources", MarketIntegrationSourceListView.as_view(), name="source-list"),
    path("market-integrations/health", MarketIntegrationHealthView.as_view(), name="source-health"),
    path("market-integrations/live-prices", NormalizedMarketPriceListView.as_view(), name="normalized-live-price-list"),
    path("market-integrations/raw-prices", RawMarketPriceListView.as_view(), name="raw-price-list"),
    path("market-integrations/prices", StoredMarketPriceListView.as_view(), name="stored-price-list"),
    path("market-integrations/import-raw", MarketIntegrationRawImportView.as_view(), name="import-raw-prices"),
    path("market-integrations/standardize", MarketIntegrationStandardizeView.as_view(), name="standardize-prices"),
    path("market-integrations/updates", MarketIntegrationUpdateCheckView.as_view(), name="update-check"),
    path("market-integrations/sync", MarketIntegrationSyncView.as_view(), name="sync-prices"),
    path(
        "market-integrations/live-prices/<str:source>",
        SourceNormalizedMarketPriceListView.as_view(),
        name="source-normalized-live-price-list",
    ),
]
