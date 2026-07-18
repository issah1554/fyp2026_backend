from __future__ import annotations

from decimal import Decimal

from django.utils import timezone

from apps.commodities.models import Market

from .forecasting import (
    COMMODITY_MAP,
    PRICE_TYPE_MAP,
    ForecastUnavailable,
    calendar_week_end_date,
    get_forecast_service,
    get_season_name,
    season_end_date,
)
from .models import UssdMarketPrediction


class CachedForecastUnavailable(ForecastUnavailable):
    pass


def get_cached_prediction(market: str, commodity: str, pricetype: str, period: str, target_date=None):
    target = target_date or timezone.localdate()
    prediction = (
        UssdMarketPrediction.objects.select_related("market")
        .filter(
            market__name=market,
            commodity=commodity,
            pricetype=pricetype,
            period=period,
            target_date=target,
        )
        .first()
    )
    if prediction is None:
        raise CachedForecastUnavailable("Not available right now.")
    return prediction


class PredictionRefreshService:
    PERIOD_SEQUENCE = ("daily", "weekly", "monthly", "seasonal")

    def __init__(self):
        self.forecaster = get_forecast_service()

    def _supported_markets(self):
        return list(
            Market.objects.filter(is_active=True, name__in=self.forecaster.supported_market_names())
            .order_by("name")
        )

    def _series_configs(self, markets):
        configs = []
        for market in markets:
            for commodity in COMMODITY_MAP.values():
                for _, (pricetype, unit) in PRICE_TYPE_MAP.items():
                    configs.append(
                        {
                            "market": market,
                            "commodity": commodity,
                            "pricetype": pricetype,
                            "unit": unit,
                        }
                    )
        return configs

    def _save_prediction(
        self,
        *,
        market,
        commodity,
        pricetype,
        unit,
        period,
        target_date,
        period_end,
        season,
        predicted_price,
        currency,
    ):
        prediction, _created = UssdMarketPrediction.objects.update_or_create(
            market=market,
            commodity=commodity,
            pricetype=pricetype,
            period=period,
            target_date=target_date,
            defaults={
                "unit": unit,
                "period_end": period_end,
                "season": season,
                "predicted_price": Decimal(str(round(predicted_price, 2))),
                "currency": currency,
            },
        )
        return prediction

    def _log_saved(self, prediction, stdout):
        if stdout is None:
            return
        stdout.write(
            (
                f"{prediction.target_date} | {prediction.market.name} | "
                f"{prediction.commodity} | {prediction.pricetype} | "
                f"{prediction.period} | {prediction.currency} "
                f"{prediction.predicted_price:,.2f}"
            )
        )

    def _log_skipped(self, failure, stdout):
        if stdout is None:
            return
        stdout.write(
            (
                f"SKIPPED | {failure['market']} | {failure['commodity']} | "
                f"{failure['pricetype']} | {failure['period']} | {failure['error']}"
            )
        )

    def _date_window(self, period, selected_date):
        import pandas as pd

        target = pd.Timestamp(selected_date).normalize()
        if period == "daily":
            return target, target
        if period == "weekly":
            return target, calendar_week_end_date(target)
        if period == "monthly":
            return target, target + pd.offsets.MonthEnd(0)
        if period == "seasonal":
            return target, season_end_date(target)
        raise ForecastUnavailable(f"Unsupported forecast period: {period}")

    def refresh_for_date(self, target_date=None, stdout=None, progress_callback=None):
        import pandas as pd

        selected_date = target_date or timezone.localdate()
        selected_timestamp = pd.Timestamp(selected_date).normalize()
        results = []
        failures = []
        daily_cache = {}

        markets = self._supported_markets()
        if not markets:
            raise ForecastUnavailable("No active supported markets found for prediction refresh.")

        series_configs = self._series_configs(markets)
        seasonal_end = season_end_date(selected_timestamp)
        season_name = get_season_name(selected_timestamp)
        def report_progress(status, config, message="", current=None, total=None, target_date=None):
            if progress_callback is None:
                return
            progress_callback(
                {
                    "status": status,
                    "market": config["market"].name,
                    "commodity": config["commodity"],
                    "pricetype": config["pricetype"],
                    "current": current,
                    "total": total,
                    "target_date": target_date,
                    "message": message,
                }
            )

        for config in series_configs:
            market = config["market"]
            commodity = config["commodity"]
            pricetype = config["pricetype"]
            unit = config["unit"]
            report_progress(config=config, status="started", message="Generating prediction series.", current=0, total=1)
            try:
                range_result = self.forecaster.predict_daily_range(
                    market=market.name,
                    commodity=commodity,
                    pricetype=pricetype,
                    start_date=selected_timestamp,
                    end_date=seasonal_end,
                    progress_callback=lambda progress, config=config: report_progress(
                        "running",
                        config,
                        f"Generating day {progress['target_date']}.",
                        current=progress["current"],
                        total=progress["total"],
                        target_date=progress["target_date"],
                    ),
                )
                daily_cache[(market.id, commodity, pricetype)] = range_result
                daily_value = range_result["predictions"][selected_timestamp.date().isoformat()]
                prediction = self._save_prediction(
                    market=market,
                    commodity=commodity,
                    pricetype=pricetype,
                    unit=unit,
                    period="daily",
                    target_date=selected_timestamp.date(),
                    period_end=selected_timestamp.date(),
                    season=season_name,
                    predicted_price=daily_value,
                    currency=range_result["currency"],
                )
                results.append(prediction)
                report_progress("completed", config, "Prediction series ready.", current=1, total=1)
            except ForecastUnavailable as exc:
                failure = {
                    "market": market.name,
                    "commodity": commodity,
                    "pricetype": pricetype,
                    "period": "daily",
                    "error": str(exc),
                }
                failures.append(failure)
                self._log_skipped(failure, stdout)
                report_progress("skipped", config, str(exc), current=1, total=1)
                continue

            range_result = daily_cache.get((market.id, commodity, pricetype))
            if range_result is None:
                continue

            self._log_saved(prediction, stdout)
            for period in ("weekly", "monthly", "seasonal"):
                window_start, window_end = self._date_window(period, selected_timestamp)
                prediction_items = [
                    price
                    for date_key, price in range_result["predictions"].items()
                    if window_start.date().isoformat() <= date_key <= window_end.date().isoformat()
                ]
                if not prediction_items:
                    failure = {
                        "market": market.name,
                        "commodity": commodity,
                        "pricetype": pricetype,
                        "period": period,
                        "error": "No daily predictions available for this period.",
                    }
                    failures.append(failure)
                    self._log_skipped(failure, stdout)
                    continue

                prediction = self._save_prediction(
                    market=market,
                    commodity=commodity,
                    pricetype=pricetype,
                    unit=unit,
                    period=period,
                    target_date=selected_timestamp.date(),
                    period_end=window_end.date(),
                    season=season_name,
                    predicted_price=sum(prediction_items) / len(prediction_items),
                    currency=range_result["currency"],
                )
                results.append(prediction)
                self._log_saved(prediction, stdout)

        return {"results": results, "failures": failures}
