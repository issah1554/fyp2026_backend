from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.views import APIView

from apps.common.responses import collection_response, mutation_response, success_response
from apps.markets.serializers import MarketCommodityPriceSerializer

from .permissions import HasMarketIntegrationPermission
from .serializers import NormalizedMarketPriceSerializer, RawCommodityPriceSerializer
from .services import aggregate_prices, available_sources, check_updates, raw_prices, source_health, stored_prices, sync_prices


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


def positive_int(value, default):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


@extend_schema(
    tags=["Market Integrations"],
    parameters=[
        OpenApiParameter("source", str, description="Optional source key: platform_a, platform_b, internal, or viwanda."),
        OpenApiParameter("commodity", str, description="Optional commodity symbol/name filter."),
        OpenApiParameter("market", str, description="Optional exact market filter."),
        OpenApiParameter("page", int, description="Page number."),
        OpenApiParameter("page_size", int, description="Items per page."),
    ],
    responses={200: NormalizedMarketPriceSerializer(many=True)},
)
class NormalizedMarketPriceListView(APIView):
    permission_classes = [HasMarketIntegrationPermission]

    def get(self, request):
        source = request.query_params.get("source")
        commodity = request.query_params.get("commodity")
        market = request.query_params.get("market")
        page_number = positive_int(request.query_params.get("page"), 1)
        page_size = min(positive_int(request.query_params.get("page_size"), 10), 100)
        
        result = aggregate_prices(source_key=source, commodity=commodity, market=market)
        records = result["records"]
        
        # Paginate in-memory
        total_items = len(records)
        total_pages = (total_items + page_size - 1) // page_size if total_items > 0 else 1
        page_number = min(page_number, total_pages)
        start_idx = (page_number - 1) * page_size
        page_records = records[start_idx : start_idx + page_size]
        
        return collection_response(
            page_records,
            meta={
                "pagination": {
                    "page": page_number,
                    "page_size": page_size,
                    "total_items": total_items,
                    "total_pages": total_pages,
                    "has_next": page_number < total_pages,
                    "has_previous": page_number > 1,
                },
                "filters": {
                    "source": source or "",
                    "commodity": commodity or "",
                    "market": market or "",
                },
                "errors": result["errors"],
            },
        )


@extend_schema(tags=["Market Integrations"], responses={200: NormalizedMarketPriceSerializer(many=True)})
class SourceNormalizedMarketPriceListView(APIView):
    permission_classes = [HasMarketIntegrationPermission]

    def get(self, request, source):
        commodity = request.query_params.get("commodity")
        market = request.query_params.get("market")
        page_number = positive_int(request.query_params.get("page"), 1)
        page_size = min(positive_int(request.query_params.get("page_size"), 10), 100)
        
        result = aggregate_prices(source_key=source, commodity=commodity, market=market)
        records = result["records"]
        
        total_items = len(records)
        total_pages = (total_items + page_size - 1) // page_size if total_items > 0 else 1
        page_number = min(page_number, total_pages)
        start_idx = (page_number - 1) * page_size
        page_records = records[start_idx : start_idx + page_size]
        
        return success_response(
            page_records,
            meta={
                "pagination": {
                    "page": page_number,
                    "page_size": page_size,
                    "total_items": total_items,
                    "total_pages": total_pages,
                    "has_next": page_number < total_pages,
                    "has_previous": page_number > 1,
                },
                "filters": {
                    "source": source,
                    "commodity": commodity or "",
                    "market": market or "",
                },
                "errors": result["errors"],
            },
        )


@extend_schema(
    tags=["Market Integrations"],
    parameters=[
        OpenApiParameter("source", str, description="Optional source key: platform_a, platform_b, internal, or viwanda."),
        OpenApiParameter("commodity", str, description="Optional commodity filter."),
        OpenApiParameter("market", str, description="Optional exact market filter."),
        OpenApiParameter("page", int, description="Page number."),
        OpenApiParameter("page_size", int, description="Items per page."),
    ],
    responses={200: MarketCommodityPriceSerializer(many=True)},
)
class StoredMarketPriceListView(APIView):
    permission_classes = [HasMarketIntegrationPermission]

    def get(self, request):
        from django.core.paginator import Paginator, EmptyPage
        source = request.query_params.get("source")
        commodity = request.query_params.get("commodity")
        market = request.query_params.get("market")
        page_number = positive_int(request.query_params.get("page"), 1)
        page_size = min(positive_int(request.query_params.get("page_size"), 10), 100)
        
        queryset = stored_prices(source_key=source, commodity=commodity, market=market)
        paginator = Paginator(queryset, page_size)
        try:
            page = paginator.page(page_number)
        except EmptyPage:
            page = paginator.page(paginator.num_pages if paginator.num_pages > 0 else 1)
            
        return collection_response(
            MarketCommodityPriceSerializer(page.object_list, many=True).data,
            meta={
                "pagination": {
                    "page": page.number,
                    "page_size": page_size,
                    "total_items": paginator.count,
                    "total_pages": paginator.num_pages,
                    "has_next": page.has_next(),
                    "has_previous": page.has_previous(),
                },
                "filters": {
                    "source": source or "",
                    "commodity": commodity or "",
                    "market": market or "",
                }
            },
        )


@extend_schema(
    tags=["Market Integrations"],
    parameters=[
        OpenApiParameter("source", str, description="Optional source key: platform_a, platform_b, internal, or viwanda."),
        OpenApiParameter("commodity", str, description="Optional commodity filter."),
        OpenApiParameter("market", str, description="Optional exact market filter."),
        OpenApiParameter("page", int, description="Page number."),
        OpenApiParameter("page_size", int, description="Items per page."),
    ],
    responses={200: RawCommodityPriceSerializer(many=True)},
)
class RawMarketPriceListView(APIView):
    permission_classes = [HasMarketIntegrationPermission]

    def get(self, request):
        from django.core.paginator import EmptyPage, Paginator

        source = request.query_params.get("source")
        commodity = request.query_params.get("commodity")
        market = request.query_params.get("market")
        page_number = positive_int(request.query_params.get("page"), 1)
        page_size = min(positive_int(request.query_params.get("page_size"), 10), 100)

        queryset = raw_prices(source_key=source, commodity=commodity, market=market)
        paginator = Paginator(queryset, page_size)
        try:
            page = paginator.page(page_number)
        except EmptyPage:
            page = paginator.page(paginator.num_pages if paginator.num_pages > 0 else 1)

        return collection_response(
            RawCommodityPriceSerializer(page.object_list, many=True).data,
            meta={
                "pagination": {
                    "page": page.number,
                    "page_size": page_size,
                    "total_items": paginator.count,
                    "total_pages": paginator.num_pages,
                    "has_next": page.has_next(),
                    "has_previous": page.has_previous(),
                },
                "filters": {
                    "source": source or "",
                    "commodity": commodity or "",
                    "market": market or "",
                },
            },
        )


@extend_schema(
    tags=["Market Integrations"],
    parameters=[
        OpenApiParameter("source", str, description="Optional source key: platform_a, platform_b, internal, or viwanda."),
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
        new_only = request.query_params.get("new_only") in ("1", "true", "True", "yes")
        result = sync_prices(source_key=source, commodity=commodity, market=market, limit=limit, new_only=new_only)
        return mutation_response(
            message="Market integration prices synced successfully.",
            data=result,
            meta={
                "filters": {
                    "source": source or "",
                    "commodity": commodity or "",
                    "market": market or "",
                    "limit": limit or "",
                    "new_only": new_only,
                }
            },
        )


@extend_schema(tags=["Market Integrations"])
class MarketIntegrationUpdateCheckView(APIView):
    permission_classes = [HasMarketIntegrationPermission]

    def get(self, request):
        source = request.query_params.get("source")
        commodity = request.query_params.get("commodity")
        market = request.query_params.get("market")
        limit = positive_limit(request.query_params.get("limit"))
        result = check_updates(source_key=source, commodity=commodity, market=market, limit=limit)
        return success_response(
            result,
            meta={
                "filters": {
                    "source": source or "",
                    "commodity": commodity or "",
                    "market": market or "",
                    "limit": limit or "",
                }
            },
        )
