from django.core.paginator import EmptyPage, Paginator
from django.db.models import OuterRef, Subquery
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.views import APIView

from apps.commodities.models import Commodity
from apps.common.responses import collection_response, mutation_response, success_response

from .models import Market, MarketCommodityPrice
from .permissions import HasMarketPermission
from .serializers import MarketCommodityPriceSerializer, MarketSerializer


DEFAULT_PAGE_SIZE = 10
MAX_PAGE_SIZE = 100


def positive_int(value, default):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def paginated_response(request, queryset, serializer_class, extra_meta=None):
    page_number = positive_int(request.query_params.get("page"), 1)
    page_size = min(positive_int(request.query_params.get("page_size"), DEFAULT_PAGE_SIZE), MAX_PAGE_SIZE)
    paginator = Paginator(queryset, page_size)
    try:
        page = paginator.page(page_number)
    except EmptyPage:
        page = paginator.page(paginator.num_pages)

    meta = {
        "pagination": {
            "page": page.number,
            "page_size": page_size,
            "total_items": paginator.count,
            "total_pages": paginator.num_pages,
            "has_next": page.has_next(),
            "has_previous": page.has_previous(),
        }
    }
    if extra_meta:
        meta.update(extra_meta)
    return collection_response(serializer_class(page.object_list, many=True).data, meta=meta)


class MarketMixin:
    permission_classes = [HasMarketPermission]

    def get_queryset(self):
        return Market.objects.select_related("admin_area", "created_by", "updated_by").all()

    def get_market(self, market_id):
        return get_object_or_404(self.get_queryset(), public_id=market_id)


@extend_schema(tags=["Markets"])
class MarketListCreateView(MarketMixin, APIView):
    permission_codes = {
        "GET": "markets.list",
        "POST": "markets.create",
    }

    @extend_schema(responses={200: MarketSerializer(many=True)})
    def get(self, request):
        queryset = self.get_queryset()
        search = request.query_params.get("search")
        status_filter = request.query_params.get("status")
        admin_area_id = request.query_params.get("admin_area_id")

        if search:
            queryset = queryset.filter(name__icontains=search)
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        if admin_area_id:
            queryset = queryset.filter(admin_area__public_id=admin_area_id)

        return paginated_response(
            request,
            queryset,
            MarketSerializer,
            extra_meta={
                "filters": {
                    "admin_area_id": admin_area_id or "",
                    "status": status_filter or "",
                },
                "search": search or "",
                "sorting": {"ordering": "name"},
            },
        )

    @extend_schema(request=MarketSerializer, responses={201: MarketSerializer})
    def post(self, request):
        serializer = MarketSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        market = serializer.save()
        return mutation_response(
            message="Market created successfully.",
            data=MarketSerializer(market).data,
            status_code=status.HTTP_201_CREATED,
        )


@extend_schema(tags=["Markets"])
class MarketDetailView(MarketMixin, APIView):
    permission_codes = {
        "GET": "markets.read",
        "PATCH": "markets.update",
        "DELETE": "markets.delete",
    }

    @extend_schema(responses={200: MarketSerializer, 404: OpenApiResponse(description="Market not found.")})
    def get(self, request, market_id):
        market = self.get_market(market_id)
        return success_response(MarketSerializer(market).data)

    @extend_schema(request=MarketSerializer, responses={200: MarketSerializer})
    def patch(self, request, market_id):
        market = self.get_market(market_id)
        serializer = MarketSerializer(market, data=request.data, partial=True, context={"request": request})
        serializer.is_valid(raise_exception=True)
        market = serializer.save()
        return mutation_response(
            message="Market updated successfully.",
            data=MarketSerializer(market).data,
            status_code=status.HTTP_200_OK,
        )

    @extend_schema(responses={200: OpenApiResponse(description="Market deleted.")})
    def delete(self, request, market_id):
        market = self.get_market(market_id)
        market.soft_delete()
        return mutation_response(message="Market deleted successfully.", status_code=status.HTTP_200_OK)


class MarketPriceMixin:
    permission_classes = [HasMarketPermission]

    def get_queryset(self):
        return MarketCommodityPrice.objects.select_related(
            "market",
            "market__admin_area",
            "commodity",
            "commodity__unit_ref",
            "created_by",
            "updated_by",
        ).prefetch_related("commodity__categories")

    def get_price(self, price_id):
        return get_object_or_404(self.get_queryset(), public_id=price_id)


@extend_schema(tags=["Market Prices"])
class MarketPriceListCreateView(MarketPriceMixin, APIView):
    permission_codes = {
        "GET": "market_prices.list",
        "POST": "market_prices.create",
    }

    @extend_schema(responses={200: MarketCommodityPriceSerializer(many=True)})
    def get(self, request):
        queryset = self.get_queryset()
        market_id = request.query_params.get("market_id")
        commodity_id = request.query_params.get("commodity_id")
        price_date = request.query_params.get("price_date")
        date_from = request.query_params.get("date_from")
        date_to = request.query_params.get("date_to")

        if market_id:
            queryset = queryset.filter(market__public_id=market_id)
        if commodity_id:
            queryset = queryset.filter(commodity__public_id=commodity_id)
        if price_date:
            queryset = queryset.filter(price_date=price_date)
        if date_from:
            queryset = queryset.filter(price_date__gte=date_from)
        if date_to:
            queryset = queryset.filter(price_date__lte=date_to)

        return paginated_response(
            request,
            queryset,
            MarketCommodityPriceSerializer,
            extra_meta={
                "filters": {
                    "market_id": market_id or "",
                    "commodity_id": commodity_id or "",
                    "price_date": price_date or "",
                    "date_from": date_from or "",
                    "date_to": date_to or "",
                },
                "sorting": {"ordering": "-price_date,market__name,commodity__name"},
            },
        )

    @extend_schema(request=MarketCommodityPriceSerializer, responses={201: MarketCommodityPriceSerializer})
    def post(self, request):
        serializer = MarketCommodityPriceSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        price = serializer.save()
        return mutation_response(
            message="Market commodity price created successfully.",
            data=MarketCommodityPriceSerializer(price).data,
            status_code=status.HTTP_201_CREATED,
        )


@extend_schema(tags=["Market Prices"])
class MarketPriceDetailView(MarketPriceMixin, APIView):
    permission_codes = {
        "GET": "market_prices.read",
        "PATCH": "market_prices.update",
        "DELETE": "market_prices.delete",
    }

    @extend_schema(responses={200: MarketCommodityPriceSerializer, 404: OpenApiResponse(description="Price not found.")})
    def get(self, request, price_id):
        price = self.get_price(price_id)
        return success_response(MarketCommodityPriceSerializer(price).data)

    @extend_schema(request=MarketCommodityPriceSerializer, responses={200: MarketCommodityPriceSerializer})
    def patch(self, request, price_id):
        price = self.get_price(price_id)
        serializer = MarketCommodityPriceSerializer(price, data=request.data, partial=True, context={"request": request})
        serializer.is_valid(raise_exception=True)
        price = serializer.save()
        return mutation_response(
            message="Market commodity price updated successfully.",
            data=MarketCommodityPriceSerializer(price).data,
            status_code=status.HTTP_200_OK,
        )

    @extend_schema(responses={200: OpenApiResponse(description="Price deleted.")})
    def delete(self, request, price_id):
        price = self.get_price(price_id)
        price.soft_delete()
        return mutation_response(message="Market commodity price deleted successfully.", status_code=status.HTTP_200_OK)


@extend_schema(tags=["Market Prices"])
class MarketNestedPriceListCreateView(MarketPriceMixin, APIView):
    permission_codes = {
        "GET": "market_prices.list",
        "POST": "market_prices.create",
    }

    @extend_schema(responses={200: MarketCommodityPriceSerializer(many=True)})
    def get(self, request, market_id):
        market = get_object_or_404(Market.objects.all(), public_id=market_id)
        queryset = self.get_queryset().filter(market=market)
        commodity_id = request.query_params.get("commodity_id")
        if commodity_id:
            queryset = queryset.filter(commodity__public_id=commodity_id)
        return paginated_response(
            request,
            queryset,
            MarketCommodityPriceSerializer,
            extra_meta={"filters": {"market_id": market_id, "commodity_id": commodity_id or ""}},
        )

    @extend_schema(request=MarketCommodityPriceSerializer, responses={201: MarketCommodityPriceSerializer})
    def post(self, request, market_id):
        market = get_object_or_404(Market.objects.all(), public_id=market_id)
        serializer = MarketCommodityPriceSerializer(
            data=request.data,
            context={"request": request},
            fixed_market=market,
        )
        serializer.is_valid(raise_exception=True)
        price = serializer.save()
        return mutation_response(
            message="Market commodity price created successfully.",
            data=MarketCommodityPriceSerializer(price).data,
            status_code=status.HTTP_201_CREATED,
        )


@extend_schema(tags=["Market Prices"])
class MarketLatestPricesView(MarketPriceMixin, APIView):
    permission_codes = {
        "GET": "market_prices.latest",
    }

    @extend_schema(responses={200: MarketCommodityPriceSerializer(many=True)})
    def get(self, request, market_id):
        market = get_object_or_404(Market.objects.all(), public_id=market_id)
        latest_price_ids = (
            MarketCommodityPrice.objects.filter(market=market, commodity=OuterRef("commodity"))
            .order_by("-price_date", "-created_at")
            .values("pk")[:1]
        )
        queryset = self.get_queryset().filter(market=market, pk__in=Subquery(latest_price_ids))
        return collection_response(
            MarketCommodityPriceSerializer(queryset, many=True).data,
            meta={"filters": {"market_id": market_id}, "sorting": {"ordering": "latest per commodity"}},
        )


@extend_schema(tags=["Commodity Prices"])
class CommodityPricesView(MarketPriceMixin, APIView):
    permission_codes = {
        "GET": "commodity_prices.list",
    }

    @extend_schema(responses={200: MarketCommodityPriceSerializer(many=True)})
    def get(self, request, commodity_id):
        get_object_or_404(Commodity.objects.all(), public_id=commodity_id)
        queryset = self.get_queryset().filter(commodity__public_id=commodity_id)
        market_id = request.query_params.get("market_id")
        if market_id:
            queryset = queryset.filter(market__public_id=market_id)
        return paginated_response(
            request,
            queryset,
            MarketCommodityPriceSerializer,
            extra_meta={"filters": {"commodity_id": commodity_id, "market_id": market_id or ""}},
        )


@extend_schema(tags=["Commodity Prices"])
class CommodityPriceHistoryView(CommodityPricesView):
    permission_codes = {
        "GET": "commodity_prices.history",
    }


@extend_schema(tags=["Commodity Prices"])
class CommodityPriceComparisonView(MarketPriceMixin, APIView):
    permission_codes = {
        "GET": "commodity_prices.compare",
    }

    @extend_schema(responses={200: MarketCommodityPriceSerializer(many=True)})
    def get(self, request, commodity_id):
        get_object_or_404(Commodity.objects.all(), public_id=commodity_id)
        price_date = request.query_params.get("price_date")
        queryset = self.get_queryset().filter(commodity__public_id=commodity_id)
        if price_date:
            queryset = queryset.filter(price_date=price_date)
            ordering_label = f"markets on {price_date}"
        else:
            latest_price_ids = (
                MarketCommodityPrice.objects.filter(commodity__public_id=commodity_id, market=OuterRef("market"))
                .order_by("-price_date", "-created_at")
                .values("pk")[:1]
            )
            queryset = queryset.filter(pk__in=Subquery(latest_price_ids))
            ordering_label = "latest per market"

        return collection_response(
            MarketCommodityPriceSerializer(queryset.order_by("price", "market__name"), many=True).data,
            meta={
                "filters": {"commodity_id": commodity_id, "price_date": price_date or ""},
                "sorting": {"ordering": ordering_label},
            },
        )
