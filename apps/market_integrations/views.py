from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.views import APIView

from apps.common.responses import collection_response, mutation_response, success_response
from apps.markets.serializers import MarketCommodityPriceSerializer

from .permissions import HasMarketIntegrationPermission
from .serializers import NormalizedMarketPriceSerializer
from .services import aggregate_prices, available_sources, source_health, stored_prices, sync_prices


def positive_limit(value):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    if parsed <= 0:
        return None
    return min(parsed, 500)


@extend_schema(tags=["Market Integrations"])
class MarketIntegrationSourceListView(APIView):
    permission_classes = [HasMarketIntegrationPermission]

    def get(self, _request):
        return collection_response(available_sources())


@extend_schema(tags=["Market Integrations"])
class MarketIntegrationHealthView(APIView):
    permission_classes = [HasMarketIntegrationPermission]

    def get(self, _request):
        results = source_health()
        return collection_response(
            results,
            meta={
                "healthy": sum(1 for item in results if item["ok"]),
                "unhealthy": sum(1 for item in results if not item["ok"]),
            },
        )


@extend_schema(
    tags=["Market Integrations"],
    parameters=[
        OpenApiParameter("source", str, description="Optional source key: platform_a, platform_b, or platform_c."),
        OpenApiParameter("commodity", str, description="Optional commodity symbol/name filter."),
        OpenApiParameter("market", str, description="Optional exact market filter."),
        OpenApiParameter("limit", int, description="Optional max records, capped at 500."),
    ],
    responses={200: NormalizedMarketPriceSerializer(many=True)},
)
class NormalizedMarketPriceListView(APIView):
    permission_classes = [HasMarketIntegrationPermission]

    def get(self, request):
        source = request.query_params.get("source")
        commodity = request.query_params.get("commodity")
        market = request.query_params.get("market")
        limit = positive_limit(request.query_params.get("limit"))
        result = aggregate_prices(source_key=source, commodity=commodity, market=market, limit=limit)
        return collection_response(
            result["records"],
            meta={
                "filters": {
                    "source": source or "",
                    "commodity": commodity or "",
                    "market": market or "",
                    "limit": limit or "",
                },
                "count": len(result["records"]),
                "errors": result["errors"],
            },
        )


@extend_schema(tags=["Market Integrations"], responses={200: NormalizedMarketPriceSerializer(many=True)})
class SourceNormalizedMarketPriceListView(APIView):
    permission_classes = [HasMarketIntegrationPermission]

    def get(self, request, source):
        commodity = request.query_params.get("commodity")
        market = request.query_params.get("market")
        limit = positive_limit(request.query_params.get("limit"))
        result = aggregate_prices(source_key=source, commodity=commodity, market=market, limit=limit)
        return success_response(
            result["records"],
            meta={
                "filters": {
                    "source": source,
                    "commodity": commodity or "",
                    "market": market or "",
                    "limit": limit or "",
                },
                "count": len(result["records"]),
                "errors": result["errors"],
            },
        )


@extend_schema(
    tags=["Market Integrations"],
    parameters=[
        OpenApiParameter("source", str, description="Optional source key: platform_a, platform_b, or platform_c."),
        OpenApiParameter("commodity", str, description="Optional commodity filter."),
        OpenApiParameter("market", str, description="Optional exact market filter."),
        OpenApiParameter("limit", int, description="Optional max records, capped at 500."),
    ],
    responses={200: MarketCommodityPriceSerializer(many=True)},
)
class StoredMarketPriceListView(APIView):
    permission_classes = [HasMarketIntegrationPermission]

    def get(self, request):
        source = request.query_params.get("source")
        commodity = request.query_params.get("commodity")
        market = request.query_params.get("market")
        limit = positive_limit(request.query_params.get("limit"))
        queryset = stored_prices(source_key=source, commodity=commodity, market=market, limit=limit)
        return collection_response(
            MarketCommodityPriceSerializer(queryset, many=True).data,
            meta={
                "filters": {
                    "source": source or "",
                    "commodity": commodity or "",
                    "market": market or "",
                    "limit": limit or "",
                }
            },
        )


@extend_schema(
    tags=["Market Integrations"],
    parameters=[
        OpenApiParameter("source", str, description="Optional source key: platform_a, platform_b, or platform_c."),
        OpenApiParameter("commodity", str, description="Optional commodity filter."),
        OpenApiParameter("market", str, description="Optional exact market filter."),
        OpenApiParameter("limit", int, description="Optional max records to import, capped at 500."),
    ],
)
class MarketIntegrationSyncView(APIView):
    permission_classes = [HasMarketIntegrationPermission]

    def post(self, request):
        source = request.query_params.get("source")
        commodity = request.query_params.get("commodity")
        market = request.query_params.get("market")
        limit = positive_limit(request.query_params.get("limit"))
        result = sync_prices(source_key=source, commodity=commodity, market=market, limit=limit)
        return mutation_response(
            message="Market integration prices synced successfully.",
            data=result,
            meta={
                "filters": {
                    "source": source or "",
                    "commodity": commodity or "",
                    "market": market or "",
                    "limit": limit or "",
                }
            },
        )
