from django.core.paginator import EmptyPage, Paginator
from django.db.models import Count, Q
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.views import APIView

from apps.common.responses import collection_response, mutation_response, success_response
from apps.markets.serializers import MarketCommodityPriceSerializer

from .permissions import HasMarketIntegrationPermission
from .serializers import NormalizedMarketPriceSerializer, RawCommodityPriceSerializer
from .services import aggregate_prices, available_sources, check_updates, import_raw_prices, raw_prices, source_health, standardize_raw_prices, stored_prices, sync_prices


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


def paginate_database_queryset(request, queryset):
    page_number = positive_int(request.query_params.get("page"), 1)
    page_size = min(positive_int(request.query_params.get("page_size"), 10), 100)
    total_items = queryset.count()
    total_pages = max((total_items + page_size - 1) // page_size, 1)
    page_number = min(page_number, total_pages)
    paginator = Paginator(queryset, page_size)

    try:
        page = paginator.page(page_number)
    except EmptyPage:
        page = paginator.page(total_pages)

    return page, {
        "page": page.number,
        "page_size": page_size,
        "total_items": total_items,
        "total_pages": total_pages,
        "has_next": page.has_next(),
        "has_previous": page.has_previous(),
    }


STORED_PRICE_ORDERING = {
    "source": "source_name",
    "market": "market__name",
    "commodity": "commodity__name",
    "price": "price",
    "price_date": "price_date",
    "created_at": "created_at",
    "raw_prices_count": "raw_prices_count",
}

RAW_PRICE_ORDERING = {
    "source": "source_name",
    "commodity": "commodity__name",
    "market": "market__name",
    "price": "price",
    "reference": "source_reference",
    "observed_at": "observed_at",
    "normalized_price_id": "normalized_price__public_id",
}


def apply_ordering(queryset, requested_ordering, allowed_fields, default_ordering):
    if not requested_ordering:
        return queryset.order_by(*default_ordering), ""

    direction = "-"
    field_key = requested_ordering
    if requested_ordering.startswith("-"):
        field_key = requested_ordering[1:]
    else:
        direction = ""

    field_name = allowed_fields.get(field_key)
    if not field_name:
        return queryset.order_by(*default_ordering), ""
    if field_name == "raw_prices_count":
        queryset = queryset.annotate(raw_prices_count=Count("raw_prices"))

    return queryset.order_by(f"{direction}{field_name}"), requested_ordering


def search_stored_prices(queryset, search):
    if not search:
        return queryset
    return queryset.filter(
        Q(source_key__icontains=search)
        | Q(source_name__icontains=search)
        | Q(market__name__icontains=search)
        | Q(commodity__name__icontains=search)
        | Q(price_type__icontains=search)
        | Q(currency__icontains=search)
    )


def search_raw_prices(queryset, search):
    if not search:
        return queryset
    return queryset.filter(
        Q(source_key__icontains=search)
        | Q(source_name__icontains=search)
        | Q(source_reference__icontains=search)
        | Q(market__name__icontains=search)
        | Q(commodity__name__icontains=search)
        | Q(price_type__icontains=search)
        | Q(currency__icontains=search)
        | Q(normalized_price__public_id__icontains=search)
    )


@extend_schema(
    tags=["Market Integrations"],
    parameters=[
        OpenApiParameter("source", str, description="Optional source key: platform_a, platform_b, internal, or viwanda."),
        OpenApiParameter("commodity", str, description="Optional commodity symbol/name filter."),
        OpenApiParameter("market", str, description="Optional exact market filter."),
        OpenApiParameter("search", str, description="Optional search across source, commodity, and market."),
        OpenApiParameter("ordering", str, description="Sort field. Prefix with - for descending."),
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
        source = request.query_params.get("source")
        commodity = request.query_params.get("commodity")
        market = request.query_params.get("market")
        search = request.query_params.get("search")
        ordering = request.query_params.get("ordering")
        
        queryset = stored_prices(source_key=source, commodity=commodity, market=market)
        queryset = search_stored_prices(queryset, search)
        queryset, applied_ordering = apply_ordering(
            queryset,
            ordering,
            STORED_PRICE_ORDERING,
            ("-price_date", "market__name", "commodity__name"),
        )
        page, pagination = paginate_database_queryset(request, queryset)
            
        return collection_response(
            MarketCommodityPriceSerializer(page.object_list, many=True).data,
            meta={
                "pagination": pagination,
                "filters": {
                    "source": source or "",
                    "commodity": commodity or "",
                    "market": market or "",
                },
                "search": search or "",
                "sorting": {"ordering": applied_ordering or "-price_date,market__name,commodity__name"},
            },
        )


@extend_schema(
    tags=["Market Integrations"],
    parameters=[
        OpenApiParameter("source", str, description="Optional source key: platform_a, platform_b, internal, or viwanda."),
        OpenApiParameter("commodity", str, description="Optional commodity filter."),
        OpenApiParameter("market", str, description="Optional exact market filter."),
        OpenApiParameter("search", str, description="Optional search across source, commodity, market, and reference."),
        OpenApiParameter("ordering", str, description="Sort field. Prefix with - for descending."),
        OpenApiParameter("page", int, description="Page number."),
        OpenApiParameter("page_size", int, description="Items per page."),
    ],
    responses={200: RawCommodityPriceSerializer(many=True)},
)
class RawMarketPriceListView(APIView):
    permission_classes = [HasMarketIntegrationPermission]

    def get(self, request):
        source = request.query_params.get("source")
        commodity = request.query_params.get("commodity")
        market = request.query_params.get("market")
        search = request.query_params.get("search")
        ordering = request.query_params.get("ordering")

        queryset = raw_prices(source_key=source, commodity=commodity, market=market)
        queryset = search_raw_prices(queryset, search)
        queryset, applied_ordering = apply_ordering(
            queryset,
            ordering,
            RAW_PRICE_ORDERING,
            ("-price_date", "market__name", "commodity__name"),
        )
        page, pagination = paginate_database_queryset(request, queryset)

        return collection_response(
            RawCommodityPriceSerializer(page.object_list, many=True).data,
            meta={
                "pagination": pagination,
                "filters": {
                    "source": source or "",
                    "commodity": commodity or "",
                    "market": market or "",
                },
                "search": search or "",
                "sorting": {"ordering": applied_ordering or "-price_date,market__name,commodity__name"},
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
class MarketIntegrationRawImportView(APIView):
    permission_classes = [HasMarketIntegrationPermission]

    def post(self, request):
        source = request.query_params.get("source")
        commodity = request.query_params.get("commodity")
        market = request.query_params.get("market")
        limit = positive_limit(request.query_params.get("limit"))
        new_only = request.query_params.get("new_only") in ("1", "true", "True", "yes")
        result = import_raw_prices(source_key=source, commodity=commodity, market=market, limit=limit, new_only=new_only)
        return mutation_response(
            message="Raw market integration prices imported successfully.",
            data=result,
            meta={"filters": {"source": source or "", "commodity": commodity or "", "market": market or "", "limit": limit or "", "new_only": new_only}},
        )


@extend_schema(tags=["Market Integrations"])
class MarketIntegrationStandardizeView(APIView):
    permission_classes = [HasMarketIntegrationPermission]

    def post(self, request):
        source = request.query_params.get("source")
        commodity = request.query_params.get("commodity")
        market = request.query_params.get("market")
        limit = positive_limit(request.query_params.get("limit"))
        result = standardize_raw_prices(source_key=source, commodity=commodity, market=market, limit=limit)
        return mutation_response(
            message="Raw market integration prices standardised successfully.",
            data=result,
            meta={"filters": {"source": source or "", "commodity": commodity or "", "market": market or "", "limit": limit or ""}},
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
