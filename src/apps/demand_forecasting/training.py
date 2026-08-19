import json
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from django.conf import settings
from django.db.models import Count, Sum
from django.db.models.functions import TruncWeek
from django.utils import timezone
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error

from apps.common.ids import generate_unique_public_id
from apps.markets.models import MarketCommodityPrice
from apps.orders.models import Order

from .models import DemandForecast, DemandForecastRun


VALID_DEMAND_STATUSES = ["completed", "confirmed", "shipped"]
FEATURE_COLUMNS = [
    "commodity_id",
    "adm_area_id",
    "year",
    "month",
    "week_of_year",
    "avg_price",
    "order_count",
    "previous_week_demand",
    "rolling_4_week_avg",
    "rolling_8_week_avg",
]


@dataclass
class TrainingResult:
    run: DemandForecastRun
    model_path: Path
    metadata_path: Path


def build_weekly_demand_frame():
    demand_rows = (
        Order.objects.filter(status__in=VALID_DEMAND_STATUSES)
        .annotate(week_start=TruncWeek("created_at"))
        .values("listing__commodity_id", "listing__adm_area_id", "week_start")
        .annotate(target_demand=Sum("quantity"), order_count=Count("id"))
        .order_by("listing__commodity_id", "listing__adm_area_id", "week_start")
    )
    df = pd.DataFrame.from_records(demand_rows)
    if df.empty:
        return df

    df = df.rename(
        columns={
            "listing__commodity_id": "commodity_id",
            "listing__adm_area_id": "adm_area_id",
        }
    )
    df["week_start"] = pd.to_datetime(df["week_start"]).dt.date
    df["target_demand"] = df["target_demand"].astype(float)
    df["order_count"] = df["order_count"].astype(int)
    return df


def attach_price_features(df):
    if df.empty:
        return df

    start_date = df["week_start"].min()
    end_date = df["week_start"].max()
    price_rows = (
        MarketCommodityPrice.objects.filter(
            commodity_id__in=df["commodity_id"].unique(),
            price_date__range=(start_date, end_date),
            deleted_at__isnull=True,
        )
        .annotate(week_start=TruncWeek("price_date"))
        .values("commodity_id", "market__admin_area_id", "week_start")
        .annotate(avg_price=Sum("price") / Count("id"))
    )
    prices = pd.DataFrame.from_records(price_rows)
    if prices.empty:
        df["avg_price"] = 0.0
        return df

    prices = prices.rename(columns={"market__admin_area_id": "adm_area_id"})
    prices["week_start"] = pd.to_datetime(prices["week_start"]).dt.date
    merged = df.merge(prices, on=["commodity_id", "adm_area_id", "week_start"], how="left")
    commodity_prices = prices.groupby("commodity_id")["avg_price"].mean().to_dict()
    merged["avg_price"] = merged.apply(
        lambda row: row["avg_price"]
        if pd.notna(row["avg_price"])
        else commodity_prices.get(row["commodity_id"], 0),
        axis=1,
    )
    merged["avg_price"] = merged["avg_price"].astype(float)
    return merged


def add_time_features(df):
    df = df.sort_values(["commodity_id", "adm_area_id", "week_start"]).copy()
    week_dates = pd.to_datetime(df["week_start"])
    iso_calendar = week_dates.dt.isocalendar()
    df["year"] = week_dates.dt.year
    df["month"] = week_dates.dt.month
    df["week_of_year"] = iso_calendar.week.astype(int)

    group_cols = ["commodity_id", "adm_area_id"]
    grouped = df.groupby(group_cols)["target_demand"]
    df["previous_week_demand"] = grouped.shift(1)
    shifted = grouped.shift(1)
    df["rolling_4_week_avg"] = shifted.groupby([df["commodity_id"], df["adm_area_id"]]).transform(
        lambda values: values.rolling(4, min_periods=1).mean()
    )
    df["rolling_8_week_avg"] = shifted.groupby([df["commodity_id"], df["adm_area_id"]]).transform(
        lambda values: values.rolling(8, min_periods=1).mean()
    )
    df[["previous_week_demand", "rolling_4_week_avg", "rolling_8_week_avg"]] = df[
        ["previous_week_demand", "rolling_4_week_avg", "rolling_8_week_avg"]
    ].fillna(0)
    return df


def build_training_frame():
    df = build_weekly_demand_frame()
    if df.empty:
        return df
    return add_time_features(attach_price_features(df))


def train_and_forecast(horizon_weeks=4, estimators=200, min_rows=200):
    run = DemandForecastRun.objects.create(status="training")
    try:
        df = build_training_frame()
        if len(df) < min_rows:
            raise ValueError(f"Not enough weekly demand rows for training: {len(df)} found, {min_rows} required.")

        df = df.sort_values("week_start")
        split_index = max(int(len(df) * 0.8), 1)
        train_df = df.iloc[:split_index]
        test_df = df.iloc[split_index:]

        model = RandomForestRegressor(
            n_estimators=estimators,
            random_state=42,
            n_jobs=-1,
            min_samples_leaf=2,
        )
        model.fit(train_df[FEATURE_COLUMNS], train_df["target_demand"])

        predictions = model.predict(test_df[FEATURE_COLUMNS]) if not test_df.empty else np.array([])
        mae = mean_absolute_error(test_df["target_demand"], predictions) if len(predictions) else 0
        rmse = mean_squared_error(test_df["target_demand"], predictions) ** 0.5 if len(predictions) else 0

        model_dir = Path(settings.BASE_DIR) / "ai-models"
        model_dir.mkdir(parents=True, exist_ok=True)
        model_path = model_dir / f"demand_forecast_{run.public_id}.joblib"
        metadata_path = model_dir / f"demand_forecast_{run.public_id}.json"
        joblib.dump({"model": model, "features": FEATURE_COLUMNS}, model_path)

        forecasts = build_forecast_rows(model, df, run, horizon_weeks)
        DemandForecast.objects.bulk_create(forecasts, batch_size=1000)

        metadata = {
            "run_id": run.public_id,
            "model_type": "RandomForestRegressor",
            "features": FEATURE_COLUMNS,
            "valid_statuses": VALID_DEMAND_STATUSES,
            "training_rows": len(train_df),
            "test_rows": len(test_df),
            "source_rows": len(df),
            "horizon_weeks": horizon_weeks,
            "mae": mae,
            "rmse": rmse,
            "trained_at": timezone.now().isoformat(),
            "forecast_rows": len(forecasts),
            "date_range": {
                "min_week": str(df["week_start"].min()),
                "max_week": str(df["week_start"].max()),
            },
        }
        metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

        run.model_path = str(model_path.relative_to(settings.BASE_DIR))
        run.metadata_path = str(metadata_path.relative_to(settings.BASE_DIR))
        run.training_finished_at = timezone.now()
        run.train_rows = len(train_df)
        run.test_rows = len(test_df)
        run.mae = Decimal(str(round(mae, 4)))
        run.rmse = Decimal(str(round(rmse, 4)))
        run.status = "completed"
        run.notes = f"Generated {len(forecasts)} forecast rows for {horizon_weeks} weeks."
        run.save()
        return TrainingResult(run=run, model_path=model_path, metadata_path=metadata_path)
    except Exception as exc:
        run.status = "failed"
        run.training_finished_at = timezone.now()
        run.notes = str(exc)
        run.save(update_fields=["status", "training_finished_at", "notes"])
        raise


def build_forecast_rows(model, df, run, horizon_weeks):
    forecasts = []
    history = df.copy()
    history["avg_price"] = history["avg_price"].astype(float)
    latest_week = max(history["week_start"])
    series_keys = history[["commodity_id", "adm_area_id"]].drop_duplicates().to_dict("records")
    price_defaults = history.groupby(["commodity_id", "adm_area_id"])["avg_price"].mean().to_dict()

    for step in range(1, horizon_weeks + 1):
        forecast_week = latest_week + timedelta(weeks=step)
        next_rows = []
        for key in series_keys:
            series = history[
                (history["commodity_id"] == key["commodity_id"])
                & (history["adm_area_id"] == key["adm_area_id"])
            ].sort_values("week_start")
            demands = series["target_demand"].tail(8).tolist()
            previous_week = demands[-1] if demands else 0
            rolling_4 = float(np.mean(demands[-4:])) if demands else 0
            rolling_8 = float(np.mean(demands[-8:])) if demands else 0
            avg_price = float(price_defaults.get((key["commodity_id"], key["adm_area_id"]), 0))
            iso = forecast_week.isocalendar()
            row = {
                "commodity_id": key["commodity_id"],
                "adm_area_id": key["adm_area_id"],
                "week_start": forecast_week,
                "year": forecast_week.year,
                "month": forecast_week.month,
                "week_of_year": iso.week,
                "avg_price": avg_price,
                "order_count": int(series["order_count"].tail(4).mean()) if not series.empty else 0,
                "previous_week_demand": previous_week,
                "rolling_4_week_avg": rolling_4,
                "rolling_8_week_avg": rolling_8,
            }
            forecast_quantity = max(0, float(model.predict(pd.DataFrame([row])[FEATURE_COLUMNS])[0]))
            row["target_demand"] = forecast_quantity
            next_rows.append(row)
            forecasts.append(
                DemandForecast(
                    public_id=generate_unique_public_id(DemandForecast),
                    run=run,
                    commodity_id=key["commodity_id"],
                    adm_area_id=key["adm_area_id"],
                    week_start=forecast_week,
                    forecast_quantity=Decimal(str(round(forecast_quantity, 2))),
                    previous_week_demand=Decimal(str(round(previous_week, 2))),
                    rolling_4_week_avg=Decimal(str(round(rolling_4, 2))),
                    rolling_8_week_avg=Decimal(str(round(rolling_8, 2))),
                    avg_price=Decimal(str(round(avg_price, 2))),
                )
            )
        history = pd.concat([history, pd.DataFrame(next_rows)], ignore_index=True)
    return forecasts
