import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_absolute_percentage_error, mean_squared_error, r2_score

from apps.markets.models import MarketCommodityPrice

FEATURE_COLUMNS = [
    "year",
    "month",
    "day",
    "dayofweek",
    "dayofyear",
    "weekofyear",
    "quarter",
    "month_sin",
    "month_cos",
    "dayofyear_sin",
    "dayofyear_cos",
    "lag_1",
    "lag_3",
    "lag_7",
    "lag_14",
    "lag_30",
    "rolling_7",
    "rolling_14",
    "rolling_30",
    "rolling_max_30",
    "rolling_min_30",
    "rolling_std_30",
    "expanding_mean",
    "pct_change_1",
    "pct_change_7",
]


class Command(BaseCommand):
    help = "Train commodity price forecasting ML models directly from MarketCommodityPrice database table."

    def add_arguments(self, parser):
        parser.add_argument(
            "--output-dir",
            default="data/price_forecasting",
            help="Directory to save price forecasting datasets/outputs. Defaults to 'data/price_forecasting'.",
        )
        parser.add_argument(
            "--model-dir",
            default="ai/models/price_forecasting",
            help="Directory to save trained price model artifacts. Defaults to 'ai/models/price_forecasting'.",
        )
        parser.add_argument(
            "--min-rows",
            type=int,
            default=120,
            help="Minimum required rows after feature engineering per series key. Defaults to 120.",
        )

    def handle(self, *args, **options):
        output_dir = Path(options["output_dir"])
        if not output_dir.is_absolute():
            output_dir = Path.cwd() / output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        model_output_dir = Path(options["model_dir"])
        if not model_output_dir.is_absolute():
            model_output_dir = Path.cwd() / model_output_dir
        outputs_dir = output_dir / "outputs"
        model_output_dir.mkdir(parents=True, exist_ok=True)
        outputs_dir.mkdir(parents=True, exist_ok=True)

        model_output_path = model_output_dir / "morogoro_price_forecaster_final.joblib"
        metrics_output_path = outputs_dir / "morogoro_price_model_metrics_final.csv"
        predictions_output_path = outputs_dir / "morogoro_price_validation_predictions_final.csv"

        self.stdout.write("Fetching historical commodity price data from database...")

        qs = MarketCommodityPrice.objects.filter(deleted_at__isnull=True).values(
            "price_date",
            "commodity__name",
            "unit__symbol",
            "price_type",
            "currency",
            "price",
        )

        if not qs.exists():
            raise CommandError("No MarketCommodityPrice records found in the database. Run import_training_prices first.")

        raw_df = pd.DataFrame.from_records(qs)
        self.stdout.write(f"Loaded {len(raw_df)} price records from database.")

        raw_df["price"] = pd.to_numeric(raw_df["price"], errors="coerce")
        raw_df["date"] = pd.to_datetime(raw_df["price_date"])
        raw_df = raw_df.dropna(subset=["date", "price"]).copy()

        raw_df["commodity"] = raw_df["commodity__name"].astype(str).str.strip()
        raw_df["unit"] = raw_df["unit__symbol"].astype(str).str.strip()
        raw_df["pricetype"] = raw_df["price_type"].astype(str).str.strip().str.title()

        series_df = (
            raw_df.groupby(["date", "commodity", "unit", "pricetype"], as_index=False)
            .agg(
                price=("price", "mean"),
                currency=("currency", "first"),
            )
            .sort_values(["commodity", "unit", "pricetype", "date"])
            .reset_index(drop=True)
        )

        series_df["series_key"] = (
            series_df["commodity"] + "|" + series_df["unit"] + "|" + series_df["pricetype"]
        )

        unique_keys = series_df["series_key"].unique()
        self.stdout.write(f"Found {len(unique_keys)} series keys: {list(unique_keys)}")

        model_bundle = {
            "source": "database_table_commodities_prices",
            "feature_columns": FEATURE_COLUMNS,
            "model_name": "random_forest_weighted",
            "models": {},
            "series_metadata": {},
        }

        metrics_rows = []
        validation_rows = []
        min_rows = options["min_rows"]

        for series_key, group in series_df.groupby("series_key"):
            group = group.sort_values("date").reset_index(drop=True)
            training_frame = self._build_training_frame(group)

            if len(training_frame) < min_rows:
                self.stdout.write(
                    self.style.WARNING(
                        f"Skipping {series_key}: only {len(training_frame)} rows after feature engineering (min {min_rows})."
                    )
                )
                continue

            split_index = max(int(len(training_frame) * 0.8), 1)
            train_split = training_frame.iloc[:split_index].copy()
            test_split = training_frame.iloc[split_index:].copy()

            X_train = train_split[FEATURE_COLUMNS]
            y_train = train_split["price"]
            X_test = test_split[FEATURE_COLUMNS]
            y_test = test_split["price"]

            train_q85 = y_train.quantile(0.85)
            train_q95 = y_train.quantile(0.95)
            sample_weights = np.where(
                y_train >= train_q95, 5.0, np.where(y_train >= train_q85, 3.0, 1.0)
            )

            test_high_threshold = y_test.quantile(0.9) if len(y_test) > 0 else 0
            high_mask_test = y_test >= test_high_threshold

            model = self._create_model()
            model.fit(X_train, y_train, sample_weight=sample_weights)
            predictions = model.predict(X_test)

            mae, rmse, r2, mape, accuracy_from_mape = self._evaluate_predictions(y_test, predictions)

            if high_mask_test.sum() > 0:
                high_mae, high_rmse, high_r2, high_mape, high_accuracy_from_mape = self._evaluate_predictions(
                    y_test[high_mask_test], predictions[high_mask_test]
                )
                high_bias = float((predictions[high_mask_test] - y_test[high_mask_test]).mean())
            else:
                high_mae = high_rmse = high_r2 = high_mape = high_accuracy_from_mape = high_bias = 0.0

            # Final model trained on full series
            final_model = self._create_model()
            full_q85 = training_frame["price"].quantile(0.85)
            full_q95 = training_frame["price"].quantile(0.95)
            full_weights = np.where(
                training_frame["price"] >= full_q95,
                5.0,
                np.where(training_frame["price"] >= full_q85, 3.0, 1.0),
            )
            final_model.fit(
                training_frame[FEATURE_COLUMNS],
                training_frame["price"],
                sample_weight=full_weights,
            )

            model_bundle["models"][series_key] = final_model
            model_bundle["series_metadata"][series_key] = {
                "commodity": group.iloc[0]["commodity"],
                "unit": group.iloc[0]["unit"],
                "pricetype": group.iloc[0]["pricetype"],
                "currency": group.iloc[0]["currency"],
                "start_date": str(group["date"].min().date()),
                "end_date": str(group["date"].max().date()),
                "sample_weight_rule": "price >= q95 => 5.0, price >= q85 => 3.0, else 1.0",
            }

            metrics_rows.append(
                {
                    "series_key": series_key,
                    "commodity": group.iloc[0]["commodity"],
                    "unit": group.iloc[0]["unit"],
                    "pricetype": group.iloc[0]["pricetype"],
                    "rows": len(training_frame),
                    "mae": round(mae, 4),
                    "rmse": round(rmse, 4),
                    "r2": round(r2, 4),
                    "mape_percent": round(mape, 4),
                    "accuracy_from_mape_percent": round(accuracy_from_mape, 4),
                    "high_price_mae": round(high_mae, 4),
                    "high_price_rmse": round(high_rmse, 4),
                    "high_price_mape_percent": round(high_mape, 4),
                    "high_price_accuracy_from_mape_percent": round(high_accuracy_from_mape, 4),
                    "high_price_bias": round(high_bias, 4),
                }
            )

            test_dates = group.iloc[split_index + len(group) - len(training_frame) :]["date"].reset_index(drop=True)
            for idx in range(len(test_split)):
                validation_rows.append(
                    {
                        "series_key": series_key,
                        "date": str(test_split.iloc[idx]["date"].date()),
                        "actual_price": float(y_test.iloc[idx]),
                        "predicted_price": float(predictions[idx]),
                        "error": float(predictions[idx] - y_test.iloc[idx]),
                        "abs_error": float(abs(predictions[idx] - y_test.iloc[idx])),
                    }
                )

            self.stdout.write(
                self.style.SUCCESS(
                    f"Trained {series_key} ({len(training_frame)} rows) -> R2: {r2:.4f}, Accuracy: {accuracy_from_mape:.2f}%"
                )
            )

        joblib.dump(model_bundle, model_output_path)
        pd.DataFrame(metrics_rows).to_csv(metrics_output_path, index=False)
        pd.DataFrame(validation_rows).to_csv(predictions_output_path, index=False)

        self.stdout.write(
            self.style.SUCCESS(
                f"Training complete!\n"
                f"Saved model bundle to: {model_output_path}\n"
                f"Saved metrics CSV to: {metrics_output_path}\n"
                f"Saved validation predictions to: {predictions_output_path}"
            )
        )

    def _add_calendar_features(self, frame: pd.DataFrame) -> pd.DataFrame:
        enriched = frame.copy()
        enriched["year"] = enriched["date"].dt.year
        enriched["month"] = enriched["date"].dt.month
        enriched["day"] = enriched["date"].dt.day
        enriched["dayofweek"] = enriched["date"].dt.dayofweek
        enriched["dayofyear"] = enriched["date"].dt.dayofyear
        enriched["weekofyear"] = enriched["date"].dt.isocalendar().week.astype(int)
        enriched["quarter"] = enriched["date"].dt.quarter
        enriched["month_sin"] = np.sin(2 * np.pi * enriched["month"] / 12)
        enriched["month_cos"] = np.cos(2 * np.pi * enriched["month"] / 12)
        enriched["dayofyear_sin"] = np.sin(2 * np.pi * enriched["dayofyear"] / 365.25)
        enriched["dayofyear_cos"] = np.cos(2 * np.pi * enriched["dayofyear"] / 365.25)
        return enriched

    def _build_training_frame(self, series_frame: pd.DataFrame) -> pd.DataFrame:
        train = series_frame[["date", "price"]].sort_values("date").copy()
        train = self._add_calendar_features(train)
        train["lag_1"] = train["price"].shift(1)
        train["lag_3"] = train["price"].shift(3)
        train["lag_7"] = train["price"].shift(7)
        train["lag_14"] = train["price"].shift(14)
        train["lag_30"] = train["price"].shift(30)
        train["rolling_7"] = train["price"].shift(1).rolling(7).mean()
        train["rolling_14"] = train["price"].shift(1).rolling(14).mean()
        train["rolling_30"] = train["price"].shift(1).rolling(30).mean()
        train["rolling_max_30"] = train["price"].shift(1).rolling(30).max()
        train["rolling_min_30"] = train["price"].shift(1).rolling(30).min()
        train["rolling_std_30"] = train["price"].shift(1).rolling(30).std()
        train["expanding_mean"] = train["price"].shift(1).expanding().mean()
        train["pct_change_1"] = train["price"].pct_change().shift(1)
        train["pct_change_7"] = train["price"].pct_change(7).shift(1)
        return train.replace([np.inf, -np.inf], np.nan).dropna().reset_index(drop=True)

    def _create_model(self) -> RandomForestRegressor:
        return RandomForestRegressor(
            n_estimators=500,
            max_depth=12,
            min_samples_leaf=2,
            random_state=42,
            n_jobs=-1,
        )

    def _evaluate_predictions(self, actual, predicted):
        if len(actual) == 0:
            return 0.0, 0.0, 0.0, 0.0, 0.0
        mae = float(mean_absolute_error(actual, predicted))
        rmse = float(np.sqrt(mean_squared_error(actual, predicted)))
        r2 = float(r2_score(actual, predicted))
        mape = float(mean_absolute_percentage_error(actual, predicted) * 100)
        accuracy_from_mape = float(max(0.0, 100.0 - mape))
        return mae, rmse, r2, mape, accuracy_from_mape
