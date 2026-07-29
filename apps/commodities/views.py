from django.core.paginator import EmptyPage, Paginator
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.views import APIView

from apps.common.responses import collection_response, mutation_response, success_response

from .models import Commodity, CommodityCategory, CommodityUnit
from .permissions import IsAdminOrAuthenticatedReadOnly
from .serializers import CommodityCategorySerializer, CommoditySerializer, CommodityUnitSerializer


DEFAULT_PAGE_SIZE = 10
MAX_PAGE_SIZE = 100


def positive_int(value, default):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def commodity_totals():
    return {
        "total": Commodity.objects.count(),
        "categories": CommodityCategory.objects.count(),
        "units": CommodityUnit.objects.count(),
        "categorized": Commodity.objects.filter(categories__isnull=False).distinct().count(),
        "uncategorized": Commodity.objects.filter(categories__isnull=True).count(),
    }
from .models import Commodity, CommodityCategory, Market, MarketPriceRecord
from .permissions import IsAdminOrAuthenticatedReadOnly, IsMarketOfficerOrAdmin
from .serializers import (
    CommodityCategorySerializer,
    CommoditySerializer,
    MarketPriceRecordSerializer,
    MarketSerializer,
)


class CommodityCategoryMixin:
    permission_classes = [IsAdminOrAuthenticatedReadOnly]

    def get_queryset(self):
        return CommodityCategory.objects.all()

    def get_category(self, category_id):
        return get_object_or_404(self.get_queryset(), public_id=category_id)


@extend_schema(tags=["Commodity Categories"])
class CommodityCategoryListCreateView(CommodityCategoryMixin, APIView):
    permission_codes = {
        "POST": "commodities.categories.create",
    }

    @extend_schema(responses={200: CommodityCategorySerializer(many=True)})
    def get(self, request):
        categories = self.get_queryset()
        return collection_response(CommodityCategorySerializer(categories, many=True).data)

    @extend_schema(request=CommodityCategorySerializer, responses={201: CommodityCategorySerializer})
    def post(self, request):
        serializer = CommodityCategorySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        category = serializer.save()
        return mutation_response(
            message="Commodity category created successfully.",
            data=CommodityCategorySerializer(category).data,
            status_code=status.HTTP_201_CREATED,
        )


@extend_schema(tags=["Commodity Categories"])
class CommodityCategoryDetailView(CommodityCategoryMixin, APIView):
    permission_codes = {
        "PATCH": "commodities.categories.update",
        "DELETE": "commodities.categories.delete",
    }

    @extend_schema(responses={200: CommodityCategorySerializer, 404: OpenApiResponse(description="Category not found.")})
    def get(self, request, category_id):
        category = self.get_category(category_id)
        return success_response(CommodityCategorySerializer(category).data)

    @extend_schema(request=CommodityCategorySerializer, responses={200: CommodityCategorySerializer})
    def patch(self, request, category_id):
        category = self.get_category(category_id)
        serializer = CommodityCategorySerializer(category, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        category = serializer.save()
        return mutation_response(
            message="Commodity category updated successfully.",
            data=CommodityCategorySerializer(category).data,
            status_code=status.HTTP_200_OK,
        )

    @extend_schema(responses={200: OpenApiResponse(description="Category deleted.")})
    def delete(self, request, category_id):
        category = self.get_category(category_id)
        category.delete()
        return mutation_response(message="Commodity category deleted successfully.", status_code=status.HTTP_200_OK)


class CommodityUnitMixin:
    permission_classes = [IsAdminOrAuthenticatedReadOnly]

    def get_queryset(self):
        return CommodityUnit.objects.all()

    def get_unit(self, unit_id):
        return get_object_or_404(self.get_queryset(), public_id=unit_id)


@extend_schema(tags=["Commodity Units"])
class CommodityUnitListCreateView(CommodityUnitMixin, APIView):
    permission_codes = {
        "POST": "commodities.units.create",
    }

    @extend_schema(responses={200: CommodityUnitSerializer(many=True)})
    def get(self, request):
        units = self.get_queryset()
        return collection_response(CommodityUnitSerializer(units, many=True).data)

    @extend_schema(request=CommodityUnitSerializer, responses={201: CommodityUnitSerializer})
    def post(self, request):
        serializer = CommodityUnitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        unit = serializer.save()
        return mutation_response(
            message="Commodity unit created successfully.",
            data=CommodityUnitSerializer(unit).data,
            status_code=status.HTTP_201_CREATED,
        )


@extend_schema(tags=["Commodity Units"])
class CommodityUnitDetailView(CommodityUnitMixin, APIView):
    permission_codes = {
        "PATCH": "commodities.units.update",
        "DELETE": "commodities.units.delete",
    }

    @extend_schema(responses={200: CommodityUnitSerializer, 404: OpenApiResponse(description="Unit not found.")})
    def get(self, request, unit_id):
        unit = self.get_unit(unit_id)
        return success_response(CommodityUnitSerializer(unit).data)

    @extend_schema(request=CommodityUnitSerializer, responses={200: CommodityUnitSerializer})
    def patch(self, request, unit_id):
        unit = self.get_unit(unit_id)
        serializer = CommodityUnitSerializer(unit, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        unit = serializer.save()
        return mutation_response(
            message="Commodity unit updated successfully.",
            data=CommodityUnitSerializer(unit).data,
            status_code=status.HTTP_200_OK,
        )

    @extend_schema(responses={200: OpenApiResponse(description="Unit deleted.")})
    def delete(self, request, unit_id):
        unit = self.get_unit(unit_id)
        unit.delete()
        return mutation_response(message="Commodity unit deleted successfully.", status_code=status.HTTP_200_OK)


class CommodityMixin:
    permission_classes = [IsAdminOrAuthenticatedReadOnly]

    def get_queryset(self):
        return Commodity.objects.prefetch_related("categories").all()

    def get_commodity(self, commodity_id):
        return get_object_or_404(self.get_queryset(), public_id=commodity_id)


@extend_schema(tags=["Commodities"])
class CommodityListCreateView(CommodityMixin, APIView):
    permission_codes = {
        "POST": "commodities.create",
    }

    @extend_schema(responses={200: CommoditySerializer(many=True)})
    def get(self, request):
        queryset = self.get_queryset()

        search = request.query_params.get("search")
        if search:
            queryset = queryset.filter(name__icontains=search)

        category_id = request.query_params.get("category_id")
        if category_id:
            queryset = queryset.filter(categories__public_id=category_id)

        page_number = positive_int(request.query_params.get("page"), 1)
        page_size = min(positive_int(request.query_params.get("page_size"), DEFAULT_PAGE_SIZE), MAX_PAGE_SIZE)
        paginator = Paginator(queryset.distinct(), page_size)

        try:
            page = paginator.page(page_number)
        except EmptyPage:
            page = paginator.page(paginator.num_pages)

        return collection_response(
            CommoditySerializer(page.object_list, many=True).data,
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
                    "category_id": category_id or "",
                },
                "sorting": {"ordering": "name"},
                "search": search or "",
                "totals": commodity_totals(),
            },
        )

    @extend_schema(request=CommoditySerializer, responses={201: CommoditySerializer})
    def post(self, request):
        serializer = CommoditySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        commodity = serializer.save()
        return mutation_response(
            message="Commodity created successfully.",
            data=CommoditySerializer(commodity).data,
            status_code=status.HTTP_201_CREATED,
        )


@extend_schema(tags=["Commodities"])
class CommodityDetailView(CommodityMixin, APIView):
    permission_codes = {
        "PATCH": "commodities.update",
        "DELETE": "commodities.delete",
    }

    @extend_schema(responses={200: CommoditySerializer, 404: OpenApiResponse(description="Commodity not found.")})
    def get(self, request, commodity_id):
        commodity = self.get_commodity(commodity_id)
        return success_response(CommoditySerializer(commodity).data)

    @extend_schema(request=CommoditySerializer, responses={200: CommoditySerializer})
    def patch(self, request, commodity_id):
        commodity = self.get_commodity(commodity_id)
        serializer = CommoditySerializer(commodity, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        commodity = serializer.save()
        return mutation_response(
            message="Commodity updated successfully.",
            data=CommoditySerializer(commodity).data,
            status_code=status.HTTP_200_OK,
        )

    @extend_schema(responses={200: OpenApiResponse(description="Commodity deleted.")})
    def delete(self, request, commodity_id):
        commodity = self.get_commodity(commodity_id)
        commodity.delete()
        return mutation_response(message="Commodity deleted successfully.", status_code=status.HTTP_200_OK)


@extend_schema(tags=["Markets"])
class MarketListView(APIView):
    permission_classes = [IsMarketOfficerOrAdmin]

    @extend_schema(responses={200: MarketSerializer(many=True)})
    def get(self, request):
        markets = Market.objects.filter(is_active=True).order_by("name")
        return collection_response(MarketSerializer(markets, many=True).data)


class MarketPriceRecordMixin:
    permission_classes = [IsMarketOfficerOrAdmin]

    def get_queryset(self):
        return (
            MarketPriceRecord.objects.select_related("market", "commodity", "created_by")
            .order_by("-record_date", "market__name", "commodity__name")
        )

    def get_record(self, record_id):
        return get_object_or_404(self.get_queryset(), public_id=record_id)


@extend_schema(tags=["Market Price Records"])
class MarketPriceRecordListCreateView(MarketPriceRecordMixin, APIView):
    @extend_schema(responses={200: MarketPriceRecordSerializer(many=True)})
    def get(self, request):
        records = self.get_queryset()
        return collection_response(MarketPriceRecordSerializer(records, many=True).data)

    @extend_schema(request=MarketPriceRecordSerializer, responses={201: MarketPriceRecordSerializer})
    def post(self, request):
        serializer = MarketPriceRecordSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        record = serializer.save()
        return mutation_response(
            message="Market price record created successfully.",
            data=MarketPriceRecordSerializer(record).data,
            status_code=status.HTTP_201_CREATED,
        )


@extend_schema(tags=["Market Price Records"])
class MarketPriceRecordDetailView(MarketPriceRecordMixin, APIView):
    @extend_schema(responses={200: MarketPriceRecordSerializer, 404: OpenApiResponse(description="Record not found.")})
    def get(self, request, record_id):
        record = self.get_record(record_id)
        return success_response(MarketPriceRecordSerializer(record).data)

    @extend_schema(request=MarketPriceRecordSerializer, responses={200: MarketPriceRecordSerializer})
    def patch(self, request, record_id):
        record = self.get_record(record_id)
        serializer = MarketPriceRecordSerializer(
            record,
            data=request.data,
            partial=True,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        record = serializer.save()
        return mutation_response(
            message="Market price record updated successfully.",
            data=MarketPriceRecordSerializer(record).data,
            status_code=status.HTTP_200_OK,
        )

    @extend_schema(responses={200: OpenApiResponse(description="Market price record deleted.")})
    def delete(self, request, record_id):
        record = self.get_record(record_id)
        record.delete()
        return mutation_response(message="Market price record deleted successfully.", status_code=status.HTTP_200_OK)
