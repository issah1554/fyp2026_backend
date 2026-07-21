from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.views import APIView

from apps.common.responses import collection_response, mutation_response, success_response
from .models import CommodityListing
from .permissions import IsSellerOrReadOnly
from .serializers import CommodityListingSerializer


class CommodityListingMixin:
    permission_classes = [IsSellerOrReadOnly]

    def get_queryset(self):
        return CommodityListing.objects.select_related("commodity", "adm_area", "user__profile").prefetch_related("images").all()

    def get_listing(self, listing_id):
        listing = get_object_or_404(self.get_queryset(), public_id=listing_id)
        self.check_object_permissions(self.request, listing)
        return listing


@extend_schema(tags=["Commodity Listings"])
class CommodityListingListCreateView(CommodityListingMixin, APIView):
    permission_codes = {
        "GET": "listings.list",
        "POST": "listings.create",
    }

    @extend_schema(responses={200: CommodityListingSerializer(many=True)})
    def get(self, request):
        queryset = self.get_queryset()
        
        # Apply filters
        commodity_id = request.query_params.get("commodity_id")
        if commodity_id:
            queryset = queryset.filter(commodity__public_id=commodity_id)
            
        area_id = request.query_params.get("area_id")
        if area_id:
            queryset = queryset.filter(adm_area__public_id=area_id)
            
        status_param = request.query_params.get("status")
        if status_param:
            queryset = queryset.filter(status=status_param)
            
        return collection_response(CommodityListingSerializer(queryset, many=True).data)

    @extend_schema(request=CommodityListingSerializer, responses={201: CommodityListingSerializer})
    def post(self, request):
        self.check_permissions(request)
        serializer = CommodityListingSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        listing = serializer.save()
        return mutation_response(
            message="Commodity listing created successfully.",
            data=CommodityListingSerializer(listing).data,
            status_code=status.HTTP_201_CREATED,
        )


@extend_schema(tags=["Commodity Listings"])
class CommodityListingDetailView(CommodityListingMixin, APIView):
    permission_codes = {
        "GET": "listings.read",
        "PATCH": "listings.update",
        "DELETE": "listings.delete",
    }

    @extend_schema(responses={200: CommodityListingSerializer, 404: OpenApiResponse(description="Listing not found.")})
    def get(self, request, listing_id):
        listing = self.get_listing(listing_id)
        return success_response(CommodityListingSerializer(listing).data)

    @extend_schema(request=CommodityListingSerializer, responses={200: CommodityListingSerializer})
    def patch(self, request, listing_id):
        listing = self.get_listing(listing_id)
        serializer = CommodityListingSerializer(listing, data=request.data, partial=True, context={"request": request})
        serializer.is_valid(raise_exception=True)
        listing = serializer.save()
        return mutation_response(
            message="Commodity listing updated successfully.",
            data=CommodityListingSerializer(listing).data,
            status_code=status.HTTP_200_OK,
        )

    @extend_schema(responses={200: OpenApiResponse(description="Listing deleted.")})
    def delete(self, request, listing_id):
        listing = self.get_listing(listing_id)
        listing.delete()
        return mutation_response(message="Commodity listing deleted successfully.", status_code=status.HTTP_200_OK)
