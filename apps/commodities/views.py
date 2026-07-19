from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.views import APIView

from apps.common.responses import collection_response, mutation_response, success_response

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


class CommodityMixin:
    permission_classes = [IsAdminOrAuthenticatedReadOnly]

    def get_queryset(self):
        return Commodity.objects.prefetch_related("categories").all()

    def get_commodity(self, commodity_id):
        return get_object_or_404(self.get_queryset(), public_id=commodity_id)


@extend_schema(tags=["Commodities"])
class CommodityListCreateView(CommodityMixin, APIView):
    @extend_schema(responses={200: CommoditySerializer(many=True)})
    def get(self, request):
        commodities = self.get_queryset()
        return collection_response(CommoditySerializer(commodities, many=True).data)

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
