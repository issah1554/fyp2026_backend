from rest_framework import serializers

from apps.areas.serializers import AdmAreaSerializer
from apps.commodities.serializers import CommoditySerializer

from .models import DemandForecast, DemandForecastRun


class DemandForecastRunSerializer(serializers.ModelSerializer):
    run_id = serializers.CharField(source="public_id", read_only=True)

    class Meta:
        model = DemandForecastRun
        fields = [
            "run_id",
            "model_type",
            "model_path",
            "training_started_at",
            "training_finished_at",
            "train_rows",
            "test_rows",
            "mae",
            "rmse",
            "status",
            "notes",
            "created_at",
        ]


class DemandForecastSerializer(serializers.ModelSerializer):
    forecast_id = serializers.CharField(source="public_id", read_only=True)
    run_id = serializers.CharField(source="run.public_id", read_only=True)
    commodity = CommoditySerializer(read_only=True)
    adm_area = AdmAreaSerializer(read_only=True)

    class Meta:
        model = DemandForecast
        fields = [
            "forecast_id",
            "run_id",
            "commodity",
            "adm_area",
            "week_start",
            "forecast_quantity",
            "previous_week_demand",
            "rolling_4_week_avg",
            "rolling_8_week_avg",
            "avg_price",
            "created_at",
        ]
