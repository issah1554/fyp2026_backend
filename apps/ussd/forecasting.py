from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from django.conf import settings
from django.utils import timezone

from apps.commodities.models import Market


MODEL_FILENAME = "morogoro_market_price_forecaster.joblib"
DEFAULT_MODEL_PATH = Path(settings.BASE_DIR) / "apps" / "ussd" / "ml" / MODEL_FILENAME

COMMODITY_MAP = {
    "1": "Beans",
    "2": "Rice",
}

PRICE_TYPE_MAP = {
    "1": ("Retail", "KG"),
    "2": ("Wholesale", "100 KG"),
}

PERIOD_MAP = {
    "1": "daily",
    "2": "weekly",
    "3": "monthly",
    "4": "seasonal",
}


class ForecastUnavailable(Exception):
    pass


def get_season_name(timestamp: pd.Timestamp) -> str:
    month = timestamp.month
    if month in (1, 2):
        return "kiangazi kifupi"
    if month in (3, 4, 5):
        return "masika"
    if month in (6, 7, 8, 9, 10):
        return "kiangazi kikuu"
    return "vuli"


def season_end_date(timestamp: pd.Timestamp) -> pd.Timestamp:
    import pandas as pd

    year = timestamp.year
    month = timestamp.month
    if month in (1, 2):
        return pd.Timestamp(year=year, month=2, day=1) + pd.offsets.MonthEnd(0)
    if month in (3, 4, 5):
        return pd.Timestamp(year=year, month=5, day=31)
    if month in (6, 7, 8, 9, 10):
        return pd.Timestamp(year=year, month=10, day=31)
    return pd.Timestamp(year=year, month=12, day=31)


def calendar_week_end_date(timestamp: pd.Timestamp) -> pd.Timestamp:
    import pandas as pd

    days_until_sunday = 6 - timestamp.dayofweek
    return timestamp + pd.Timedelta(days=days_until_sunday)


def add_calendar_features(frame: pd.DataFrame) -> pd.DataFrame:
    import numpy as np

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


def build_feature_row(history: pd.DataFrame, target_date: pd.Timestamp, feature_columns: list[str]) -> pd.DataFrame:
    import numpy as np
    import pandas as pd

    price_history = history["price"].tolist()
    if len(price_history) < 30:
        raise ForecastUnavailable("Not enough historical observations to forecast.")

    frame = pd.DataFrame({"date": [target_date]})
    frame = add_calendar_features(frame)
    frame["lag_1"] = price_history[-1]
    frame["lag_3"] = price_history[-3]
    frame["lag_7"] = price_history[-7]
    frame["lag_14"] = price_history[-14]
    frame["lag_30"] = price_history[-30]
    frame["rolling_7"] = float(np.mean(price_history[-7:]))
    frame["rolling_14"] = float(np.mean(price_history[-14:]))
    frame["rolling_30"] = float(np.mean(price_history[-30:]))
    frame["rolling_max_30"] = float(np.max(price_history[-30:]))
    frame["rolling_min_30"] = float(np.min(price_history[-30:]))
    frame["rolling_std_30"] = float(np.std(price_history[-30:], ddof=1))
    frame["expanding_mean"] = float(np.mean(price_history))

    current_price = price_history[-1]
    frame["pct_change_1"] = 0.0 if current_price == 0 else float((price_history[-1] - price_history[-2]) / price_history[-2])
    frame["pct_change_7"] = (
        0.0
        if price_history[-8] == 0
        else float((price_history[-1] - price_history[-8]) / price_history[-8])
    )
    return frame[feature_columns]


@dataclass
class ForecastResult:
    market: str
    commodity: str
    pricetype: str
    unit: str
    period: str
    target_date: str
    period_end: str
    season: str
    predicted_price: float
    currency: str


class MarketPriceForecaster:
    def __init__(self, model_path: Path | None = None):
        self.model_path = Path(model_path or DEFAULT_MODEL_PATH)
        self._bundle = None

    def _load_bundle(self):
        if self._bundle is not None:
            return self._bundle
        if not self.model_path.exists():
            raise ForecastUnavailable(f"Forecast model not found at {self.model_path}.")
        import joblib

        try:
            self._bundle = joblib.load(self.model_path)
        except Exception as exc:
            raise ForecastUnavailable(
                "Forecast model could not be loaded on this server."
            ) from exc
        return self._bundle

    def _series_key(self, market: str, commodity: str, pricetype: str) -> str:
        return f"{market}|{commodity}|{pricetype}"

    def supported_market_names(self) -> list[str]:
        bundle = self._load_bundle()
        return sorted({key.split("|", 1)[0] for key in bundle["series_metadata"].keys()})

    def get_market_options(self) -> list[tuple[str, str]]:
        markets = list(
            Market.objects.filter(is_active=True)
            .order_by("name")
            .values_list("name", flat=True)
        )
        return [(str(index), name) for index, name in enumerate(markets, start=1)]

    def _predict_daily(self, series_key: str, target_date: pd.Timestamp) -> float:
        import pandas as pd

        bundle = self._load_bundle()
        models = bundle["models"]
        histories = bundle["histories"]
        feature_columns = bundle["feature_columns"]

        if series_key not in models or series_key not in histories:
            raise ForecastUnavailable(f"No forecast series available for {series_key}.")

        model = models[series_key]
        history = histories[series_key].copy().sort_values("date").reset_index(drop=True)
        history["date"] = pd.to_datetime(history["date"])

        max_date = history["date"].max()
        if target_date <= max_date:
            prior_history = history[history["date"] < target_date].copy().reset_index(drop=True)
            if prior_history.empty:
                raise ForecastUnavailable("Target date is too early for forecasting.")
            feature_row = build_feature_row(prior_history, target_date, feature_columns)
            return float(model.predict(feature_row)[0])

        recursive_history = history.copy()
        for date_value in pd.date_range(max_date + pd.Timedelta(days=1), target_date, freq="D"):
            feature_row = build_feature_row(recursive_history, date_value, feature_columns)
            prediction = float(model.predict(feature_row)[0])
            recursive_history = pd.concat(
                [recursive_history, pd.DataFrame({"date": [date_value], "price": [prediction]})],
                ignore_index=True,
            )
        return float(recursive_history.loc[recursive_history["date"] == target_date, "price"].iloc[0])

    def predict_daily_range(
        self,
        market: str,
        commodity: str,
        pricetype: str,
        start_date,
        end_date,
        progress_callback=None,
    ) -> dict:
        import pandas as pd

        bundle = self._load_bundle()
        metadata = bundle["series_metadata"]
        models = bundle["models"]
        histories = bundle["histories"]
        feature_columns = bundle["feature_columns"]

        prediction_start = pd.Timestamp(start_date).normalize()
        prediction_end = pd.Timestamp(end_date).normalize()
        if prediction_end < prediction_start:
            raise ForecastUnavailable("End date must not be before start date.")

        series_key = self._series_key(market, commodity, pricetype)
        if series_key not in metadata or series_key not in models or series_key not in histories:
            raise ForecastUnavailable(f"No prediction data for {market}, {commodity}, {pricetype}.")

        model = models[series_key]
        history = histories[series_key].copy().sort_values("date").reset_index(drop=True)
        history["date"] = pd.to_datetime(history["date"])

        prior_history = history[history["date"] < prediction_start].copy().reset_index(drop=True)
        if prior_history.empty:
            raise ForecastUnavailable("Target date is too early for forecasting.")

        recursive_history = prior_history
        max_known_date = recursive_history["date"].max()
        if prediction_start > max_known_date + pd.Timedelta(days=1):
            for warmup_date in pd.date_range(max_known_date + pd.Timedelta(days=1), prediction_start - pd.Timedelta(days=1), freq="D"):
                feature_row = build_feature_row(recursive_history, warmup_date, feature_columns)
                warmup_prediction = float(model.predict(feature_row)[0])
                recursive_history = pd.concat(
                    [recursive_history, pd.DataFrame({"date": [warmup_date], "price": [warmup_prediction]})],
                    ignore_index=True,
                )

        predictions = {}
        total_days = len(pd.date_range(prediction_start, prediction_end, freq="D"))
        for index, date_value in enumerate(pd.date_range(prediction_start, prediction_end, freq="D"), start=1):
            if progress_callback is not None:
                progress_callback(
                    {
                        "status": "running",
                        "current": index - 1,
                        "total": total_days,
                        "target_date": date_value.date().isoformat(),
                    }
                )
            feature_row = build_feature_row(recursive_history, date_value, feature_columns)
            prediction = float(model.predict(feature_row)[0])
            recursive_history = pd.concat(
                [recursive_history, pd.DataFrame({"date": [date_value], "price": [prediction]})],
                ignore_index=True,
            )
            predictions[date_value.date().isoformat()] = prediction
            if progress_callback is not None:
                progress_callback(
                    {
                        "status": "running",
                        "current": index,
                        "total": total_days,
                        "target_date": date_value.date().isoformat(),
                    }
                )
        return {
            "market": market,
            "commodity": commodity,
            "pricetype": pricetype,
            "predictions": predictions,
            "currency": metadata[series_key]["currency"],
        }

    def predict(self, market: str, commodity: str, pricetype: str, unit: str, period: str, target_date=None) -> ForecastResult:
        import numpy as np
        import pandas as pd

        bundle = self._load_bundle()
        metadata = bundle["series_metadata"]

        prediction_date = pd.Timestamp(target_date or timezone.localdate()).normalize()
        series_key = self._series_key(market, commodity, pricetype)
        if series_key not in metadata:
            raise ForecastUnavailable(f"No prediction data for {market}, {commodity}, {pricetype}.")

        if period == "daily":
            period_end = prediction_date
            predicted_value = self._predict_daily(series_key, prediction_date)
        elif period == "weekly":
            period_end = calendar_week_end_date(prediction_date)
            values = [self._predict_daily(series_key, day) for day in pd.date_range(prediction_date, period_end, freq="D")]
            predicted_value = float(np.mean(values))
        elif period == "monthly":
            period_end = prediction_date + pd.offsets.MonthEnd(0)
            values = [self._predict_daily(series_key, day) for day in pd.date_range(prediction_date, period_end, freq="D")]
            predicted_value = float(np.mean(values))
        elif period == "seasonal":
            period_end = season_end_date(prediction_date)
            values = [self._predict_daily(series_key, day) for day in pd.date_range(prediction_date, period_end, freq="D")]
            predicted_value = float(np.mean(values))
        else:
            raise ForecastUnavailable(f"Unsupported forecast period: {period}")

        return ForecastResult(
            market=market,
            commodity=commodity,
            pricetype=pricetype,
            unit=unit,
            period=period,
            target_date=prediction_date.date().isoformat(),
            period_end=period_end.date().isoformat(),
            season=get_season_name(prediction_date),
            predicted_price=predicted_value,
            currency=metadata[series_key]["currency"],
        )


@lru_cache(maxsize=1)
def get_forecast_service() -> MarketPriceForecaster:
    return MarketPriceForecaster()
