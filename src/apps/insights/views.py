from decimal import Decimal

from django.db.models import Avg, Count, Max, Min, Sum
from drf_spectacular.utils import extend_schema
from rest_framework.views import APIView

from apps.common.permissions import PublicReadPermissionCode
from apps.common.responses import success_response
from apps.listings.models import CommodityListing
from apps.markets.models import MarketCommodityPrice
from apps.orders.models import Order


SERIES_LIMIT = 10
REPORT_ROW_LIMIT = 500


def decimal_value(value):
    if value is None:
        return 0
    if isinstance(value, Decimal):
        return float(value)
    return value


def series_row(row, key_name="key", value_name="value"):
    return {
        "key": row.get(key_name) or "Unknown",
        "value": decimal_value(row.get(value_name)),
        "count": row.get("count", 0),
    }


def price_queryset():
    return MarketCommodityPrice.objects.select_related("market", "commodity").all()


def listing_queryset():
    return CommodityListing.objects.select_related("commodity", "adm_area", "user").all()


def order_queryset():
    return Order.objects.select_related("listing", "listing__commodity", "user").all()


def build_visualization_payload():
    prices = price_queryset()
    listings = listing_queryset()
    orders = order_queryset()
    price_stats = prices.aggregate(
        average_price=Avg("price"),
        min_price=Min("price"),
        max_price=Max("price"),
        latest_price_date=Max("price_date"),
    )

    price_by_commodity = [
        series_row(row, "commodity__name", "value")
        for row in prices.values("commodity__name")
        .annotate(value=Avg("price"), count=Count("id"))
        .order_by("-value")[:SERIES_LIMIT]
    ]
    price_by_market = [
        series_row(row, "market__name", "value")
        for row in prices.values("market__name")
        .annotate(value=Avg("price"), count=Count("id"))
        .order_by("-value")[:SERIES_LIMIT]
    ]
    daily_average_prices = [
        series_row(row, "price_date", "value")
        for row in prices.values("price_date")
        .annotate(value=Avg("price"), count=Count("id"))
        .order_by("-price_date")[:SERIES_LIMIT]
    ]
    daily_average_prices.reverse()

    listing_quantity_by_commodity = [
        series_row(row, "commodity__name", "value")
        for row in listings.values("commodity__name")
        .annotate(value=Sum("quantity"), count=Count("id"))
        .order_by("-value")[:SERIES_LIMIT]
    ]
    listing_quantity_by_area = [
        series_row(row, "adm_area__name", "value")
        for row in listings.values("adm_area__name")
        .annotate(value=Sum("quantity"), count=Count("id"))
        .order_by("-value")[:SERIES_LIMIT]
    ]
    order_quantity_by_commodity = [
        series_row(row, "listing__commodity__name", "value")
        for row in orders.values("listing__commodity__name")
        .annotate(value=Sum("quantity"), count=Count("id"))
        .order_by("-value")[:SERIES_LIMIT]
    ]
    order_value_by_commodity = [
        series_row(row, "listing__commodity__name", "value")
        for row in orders.values("listing__commodity__name")
        .annotate(value=Sum("total_price"), count=Count("id"))
        .order_by("-value")[:SERIES_LIMIT]
    ]

    return {
        "totals": {
            "price_rows": prices.count(),
            "listing_rows": listings.count(),
            "order_rows": orders.count(),
            "commodities_tracked": prices.values("commodity_id").distinct().count(),
            "markets_tracked": prices.values("market_id").distinct().count(),
            "latest_price_date": price_stats["latest_price_date"].isoformat() if price_stats["latest_price_date"] else None,
            "average_price": decimal_value(price_stats["average_price"]),
            "min_price": decimal_value(price_stats["min_price"]),
            "max_price": decimal_value(price_stats["max_price"]),
            "total_listed_quantity": decimal_value(listings.aggregate(value=Sum("quantity"))["value"]),
            "total_order_value": decimal_value(orders.aggregate(value=Sum("total_price"))["value"]),
        },
        "price_by_commodity": price_by_commodity,
        "price_by_market": price_by_market,
        "daily_average_prices": [
            {**item, "key": item["key"].isoformat() if hasattr(item["key"], "isoformat") else item["key"]}
            for item in daily_average_prices
        ],
        "listing_quantity_by_commodity": listing_quantity_by_commodity,
        "listing_quantity_by_area": listing_quantity_by_area,
        "order_quantity_by_commodity": order_quantity_by_commodity,
        "order_value_by_commodity": order_value_by_commodity,
    }


def build_reporting_payload():
    prices = price_queryset().order_by("-price_date", "market__name", "commodity__name")[:REPORT_ROW_LIMIT]
    listings = listing_queryset().order_by("-created_at")[:REPORT_ROW_LIMIT]
    orders = order_queryset().order_by("-created_at")[:REPORT_ROW_LIMIT]

    return {
        **build_visualization_payload(),
        "report_rows": {
            "prices": [
                {
                    "commodity": price.commodity.name,
                    "market": price.market.name,
                    "price": decimal_value(price.price),
                    "min_price": decimal_value(price.min_price),
                    "max_price": decimal_value(price.max_price),
                    "currency": price.currency,
                    "source": price.source_name or price.source_key or "Manual",
                    "price_date": price.price_date.isoformat(),
                }
                for price in prices
            ],
            "listings": [
                {
                    "commodity": listing.commodity.name,
                    "area": listing.adm_area.name,
                    "quantity": decimal_value(listing.quantity),
                    "price": decimal_value(listing.price),
                    "seller": listing.user.get_full_name() if listing.user_id else "-",
                    "status": listing.status,
                    "created_at": listing.created_at.isoformat(),
                }
                for listing in listings
            ],
            "orders": [
                {
                    "commodity": order.listing.commodity.name,
                    "buyer": order.user.get_full_name() if order.user_id else "-",
                    "quantity": decimal_value(order.quantity),
                    "total_price": decimal_value(order.total_price),
                    "status": order.status,
                    "created_at": order.created_at.isoformat(),
                }
                for order in orders
            ],
        },
    }


@extend_schema(tags=["Insights"])
class InsightVisualizationView(APIView):
    permission_classes = [PublicReadPermissionCode]

    @extend_schema(responses={200: dict})
    def get(self, request):
        return success_response(build_visualization_payload())


@extend_schema(tags=["Insights"])
class InsightReportingView(APIView):
    permission_classes = [PublicReadPermissionCode]

    @extend_schema(responses={200: dict})
    def get(self, request):
        return success_response(build_reporting_payload())

