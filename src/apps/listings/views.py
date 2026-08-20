from django.core.paginator import EmptyPage, Paginator
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.views import APIView

from apps.areas.models import AdmArea
from apps.common.responses import collection_response, mutation_response, success_response
from .models import CommodityListing, ListingImage
from .permissions import IsSellerOrReadOnly
from .serializers import CommodityListingSerializer, ListingImageSerializer, ListingImageUploadSerializer


DEFAULT_PAGE_SIZE = 9
MAX_PAGE_SIZE = 100


def positive_int(value, default):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


class CommodityListingMixin:
    permission_classes = [IsSellerOrReadOnly]

    def get_queryset(self):
        return CommodityListing.objects.select_related("commodity", "adm_area", "user__profile").prefetch_related("images", "user__profile__roles").all()

    def get_listing(self, listing_id):
        listing = get_object_or_404(self.get_queryset(), public_id=listing_id)
        self.check_object_permissions(self.request, listing)
        return listing


@extend_schema(tags=["Commodity Listings"])
class CommodityListingListCreateView(CommodityListingMixin, APIView):
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    permission_codes = {
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
            area = AdmArea.objects.filter(public_id=area_id).first()
            if area is None:
                queryset = queryset.none()
            else:
                queryset = queryset.filter(adm_area_id__in=area.descendant_ids())
            
        status_param = request.query_params.get("status")
        if status_param:
            queryset = queryset.filter(status=status_param)

        min_price = request.query_params.get("min_price")
        if min_price:
            queryset = queryset.filter(price__gte=min_price)

        max_price = request.query_params.get("max_price")
        if max_price:
            queryset = queryset.filter(price__lte=max_price)

        ordering_param = request.query_params.get("ordering")
        ordering_map = {
            "price": "price",
            "-price": "-price",
            "created_at": "created_at",
            "-created_at": "-created_at",
        }
        ordering = ordering_map.get(ordering_param, "-created_at")
        queryset = queryset.order_by(ordering, "-id")

        page_number = positive_int(request.query_params.get("page"), 1)
        page_size = min(positive_int(request.query_params.get("page_size"), DEFAULT_PAGE_SIZE), MAX_PAGE_SIZE)
        paginator = Paginator(queryset, page_size)

        try:
            page = paginator.page(page_number)
        except EmptyPage:
            page = paginator.page(paginator.num_pages)

        return collection_response(
            CommodityListingSerializer(page.object_list, many=True).data,
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
                    "commodity_id": commodity_id or "",
                    "area_id": area_id or "",
                    "status": status_param or "",
                    "min_price": min_price or "",
                    "max_price": max_price or "",
                },
                "sorting": {"ordering": ordering},
                "search": "",
                "counts": {"total": paginator.count},
            },
        )

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
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    permission_codes = {
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


@extend_schema(tags=["Commodity Listings"])
class ListingImageListCreateView(CommodityListingMixin, APIView):
    parser_classes = [MultiPartParser, FormParser]
    permission_codes = {
        "POST": "listings.update",
    }

    @extend_schema(request=ListingImageUploadSerializer, responses={201: ListingImageSerializer(many=True)})
    def post(self, request, listing_id):
        listing = self.get_listing(listing_id)
        serializer = ListingImageUploadSerializer(
            data=request.data,
            context={"request": request, "listing": listing},
        )
        serializer.is_valid(raise_exception=True)
        images = serializer.save()
        return mutation_response(
            message="Listing image(s) added successfully.",
            data=ListingImageSerializer(images, many=True).data,
            status_code=status.HTTP_201_CREATED,
        )


@extend_schema(tags=["Commodity Listings"])
class ListingImageDetailView(CommodityListingMixin, APIView):
    permission_codes = {
        "DELETE": "listings.update",
    }

    @extend_schema(responses={200: OpenApiResponse(description="Listing image deleted.")})
    def delete(self, request, listing_id, image_id):
        listing = self.get_listing(listing_id)
        image = get_object_or_404(ListingImage, listing=listing, public_id=image_id)
        if listing.images.count() <= 3:
            from rest_framework.exceptions import ValidationError

            raise ValidationError({"images": ["A listing must keep at least 3 images."]})

        was_primary = image.is_primary
        image.delete()
        if was_primary:
            next_image = listing.images.order_by("created_at").first()
            if next_image:
                next_image.is_primary = True
                next_image.save(update_fields=["is_primary"])

        return mutation_response(message="Listing image deleted successfully.", status_code=status.HTTP_200_OK)
