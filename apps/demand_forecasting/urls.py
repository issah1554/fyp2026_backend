from django.urls import path

from .views import DemandForecastListView, DemandForecastRunListView, DemandForecastTrainView

app_name = "demand_forecasting"

urlpatterns = [
    path("demand-forecasts", DemandForecastListView.as_view(), name="demand-forecast-list"),
    path("demand-forecasts/runs", DemandForecastRunListView.as_view(), name="demand-forecast-run-list"),
    path("demand-forecasts/train", DemandForecastTrainView.as_view(), name="demand-forecast-train"),
]

