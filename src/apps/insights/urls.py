from django.urls import path

from .views import InsightReportingView, InsightVisualizationView


app_name = "insights"

urlpatterns = [
    path("insights/visualization", InsightVisualizationView.as_view(), name="insight-visualization"),
    path("insights/reporting", InsightReportingView.as_view(), name="insight-reporting"),
]

