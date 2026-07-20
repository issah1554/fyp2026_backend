from django.urls import path

from .views import (
    CommodityListingDetailView,
    CommodityListingListCreateView,
)

app_name = "listings"

urlpatterns = [
    path("listings", CommodityListingListCreateView.as_view(), name="listing-list"),
    path("listings/<str:listing_id>", CommodityListingDetailView.as_view(), name="listing-detail"),
]
