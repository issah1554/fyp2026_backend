from django.urls import path

from .views import (
    AdmAreaDetailView,
    AdmAreaListCreateView,
    CommodityListingDetailView,
    CommodityListingListCreateView,
)

app_name = "listings"

urlpatterns = [
    path("areas/", AdmAreaListCreateView.as_call_view() if hasattr(AdmAreaListCreateView, "as_call_view") else AdmAreaListCreateView.as_view(), name="area-list"),
    path("areas/<str:area_id>/", AdmAreaDetailView.as_view(), name="area-detail"),
    path("listings/", CommodityListingListCreateView.as_view(), name="listing-list"),
    path("listings/<str:listing_id>/", CommodityListingDetailView.as_view(), name="listing-detail"),
]
