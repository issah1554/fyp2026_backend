from django.db import models
from django.utils import timezone

from apps.common.ids import generate_unique_public_id


class DemandForecastRun(models.Model):
    public_id = models.CharField(max_length=10, unique=True, editable=False)
    model_type = models.CharField(max_length=100, default="RandomForestRegressor")
    model_path = models.CharField(max_length=255, blank=True)
    training_started_at = models.DateTimeField(default=timezone.now)
    training_finished_at = models.DateTimeField(null=True, blank=True)
    train_rows = models.PositiveIntegerField(default=0)
    test_rows = models.PositiveIntegerField(default=0)
    mae = models.DecimalField(max_digits=14, decimal_places=4, null=True, blank=True)
    rmse = models.DecimalField(max_digits=14, decimal_places=4, null=True, blank=True)
    status = models.CharField(max_length=50, default="training")
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "demand_forecast_runs"
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if not self.public_id:
            self.public_id = generate_unique_public_id(DemandForecastRun)
            if kwargs.get("update_fields") is not None:
                kwargs["update_fields"] = set(kwargs["update_fields"]) | {"public_id"}
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.model_type} run {self.public_id}"


class DemandForecast(models.Model):
    public_id = models.CharField(max_length=10, unique=True, editable=False)
    run = models.ForeignKey(
        DemandForecastRun,
        on_delete=models.CASCADE,
        related_name="forecasts",
    )
    commodity = models.ForeignKey(
        "commodities.Commodity",
        on_delete=models.CASCADE,
        related_name="demand_forecasts",
    )
    adm_area = models.ForeignKey(
        "areas.AdmArea",
        on_delete=models.CASCADE,
        related_name="demand_forecasts",
    )
    week_start = models.DateField()
    forecast_quantity = models.DecimalField(max_digits=14, decimal_places=2)
    previous_week_demand = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    rolling_4_week_avg = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    rolling_8_week_avg = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    avg_price = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "demand_forecasts"
        ordering = ["week_start", "commodity__name", "adm_area__name"]
        indexes = [
            models.Index(fields=["run", "week_start"], name="df_run_week_idx"),
            models.Index(fields=["commodity", "adm_area", "week_start"], name="df_commodity_area_week_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["run", "commodity", "adm_area", "week_start"],
                name="unique_demand_forecast_row",
            )
        ]

    def save(self, *args, **kwargs):
        if not self.public_id:
            self.public_id = generate_unique_public_id(DemandForecast)
            if kwargs.get("update_fields") is not None:
                kwargs["update_fields"] = set(kwargs["update_fields"]) | {"public_id"}
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.commodity} demand at {self.adm_area} for {self.week_start}"
