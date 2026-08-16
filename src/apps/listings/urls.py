from django.urls import path

from .views import (
    CommodityListingDetailView,
    CommodityListingListCreateView,
    ListingImageDetailView,
    ListingImageListCreateView,
)

app_name = "listings"

urlpatterns = [
    path("listings", CommodityListingListCreateView.as_view(), name="listing-list"),
    path("listings/<str:listing_id>", CommodityListingDetailView.as_view(), name="listing-detail"),
    path("listings/<str:listing_id>/images", ListingImageListCreateView.as_view(), name="listing-image-list"),
    path("listings/<str:listing_id>/images/<str:image_id>", ListingImageDetailView.as_view(), name="listing-image-detail"),
]
