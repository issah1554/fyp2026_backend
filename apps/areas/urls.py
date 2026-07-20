from django.urls import path

from .views import AdmAreaBulkCreateView, AdmAreaDetailView, AdmAreaListCreateView

app_name = "areas"

urlpatterns = [
    path("areas", AdmAreaListCreateView.as_view(), name="area-list"),
    path("areas/bulk", AdmAreaBulkCreateView.as_view(), name="area-bulk-create"),
    path("areas/<str:area_id>", AdmAreaDetailView.as_view(), name="area-detail"),
]
