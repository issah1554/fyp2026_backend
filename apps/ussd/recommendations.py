from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from datetime import timedelta

from django.utils import timezone

from .forecasting import calendar_week_end_date, get_forecast_service, season_end_date
from .models import UssdMarketPrediction, UssdMarketRecommendation, UssdSubscriber


RETAIL_PRICE_TYPE = UssdMarketPrediction.PriceType.RETAIL
LOW_PRICE_POSITION = Decimal("0.25")
HIGH_PRICE_POSITION = Decimal("0.75")
MIN_MEANINGFUL_SPREAD = Decimal("1.00")
WAIT_THRESHOLD = Decimal("1.00")


def _as_decimal(value) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _normalize_to_kg(prediction: UssdMarketPrediction) -> Decimal:
    price = _as_decimal(prediction.predicted_price)
    if prediction.unit.upper() == "100 KG":
        return price / Decimal("100")
    return price


def _round_money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _round_confidence(value: Decimal) -> Decimal:
    clamped = max(Decimal("50.00"), min(Decimal("95.00"), value))
    return clamped.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _percent_change(current: Decimal, baseline: Decimal) -> Decimal:
    if baseline == 0:
        return Decimal("0.00")
    return ((current - baseline) / baseline) * Decimal("100")


def _trend_from_change(change_pct: Decimal) -> str:
    if change_pct >= Decimal("1.50"):
        return UssdMarketRecommendation.Trend.RISING
    if change_pct <= Decimal("-1.50"):
        return UssdMarketRecommendation.Trend.FALLING
    return UssdMarketRecommendation.Trend.STABLE


def _format_period(period: str) -> str:
    return {
        "daily": "today",
        "weekly": "this week",
        "monthly": "this month",
        "seasonal": "this season",
    }[period]


def _period_end(period: str, selected_date):
    import pandas as pd

    target = pd.Timestamp(selected_date).normalize()
    if period == "daily":
        return target.date()
    if period == "weekly":
        return calendar_week_end_date(target).date()
    if period == "monthly":
        return (target + pd.offsets.MonthEnd(0)).date()
    return season_end_date(target).date()


def _average_prices(items) -> Decimal:
    return sum(price for _date_key, price in items) / Decimal(len(items))


def _format_window(start_date, end_date) -> str:
    if start_date == end_date:
        return start_date.isoformat()
    return f"{start_date.isoformat()} to {end_date.isoformat()}"


def _range_spread_pct(lowest: Decimal, highest: Decimal) -> Decimal:
    if lowest == 0:
        return Decimal("0.00")
    return ((highest - lowest) / lowest) * Decimal("100")


def _price_position(value: Decimal, lowest: Decimal, highest: Decimal) -> Decimal:
    if highest == lowest:
        return Decimal("0.50")
    return (value - lowest) / (highest - lowest)


def get_cached_recommendation(role: str, commodity: str, recommendation_type: str, target_date=None):
    target = target_date or timezone.localdate()
    recommendation = UssdMarketRecommendation.objects.select_related("market").filter(
        role=role,
        commodity=commodity,
        recommendation_type=recommendation_type,
        target_date=target,
    ).first()
    if recommendation is None:
        raise LookupError("Recommendation not available right now.")
    return recommendation


class RecommendationRefreshService:
    RECOMMENDATION_TYPES = ("time", "market")
    ROLE_CONFIG = {
        UssdSubscriber.Role.BUYER: UssdMarketRecommendation.Action.BUY,
        UssdSubscriber.Role.FARMER: UssdMarketRecommendation.Action.SELL,
        UssdSubscriber.Role.ENTREPRENEUR: UssdMarketRecommendation.Action.SELL,
    }

    def __init__(self, forecast_service):
        self.forecast_service = forecast_service
        self._series_cache = {}

    def _supported_commodities(self) -> list[str]:
        return self.forecast_service.get_supported_commodity_names()

    def _supported_markets(self) -> list[str]:
        return [name for _option, name in self.forecast_service.get_market_options()]

    def _load_predictions(self, target_date):
        predictions = (
            UssdMarketPrediction.objects.select_related("market")
            .filter(
                target_date=target_date,
                commodity__in=self._supported_commodities(),
                pricetype=RETAIL_PRICE_TYPE,
            )
            .order_by("commodity", "market__name", "period", "pricetype")
        )
        grouped = {}
        for prediction in predictions:
            grouped.setdefault(prediction.commodity, []).append(prediction)
        return grouped

    def _load_retail_series(self, target_date) -> dict[str, dict]:
        cache_key = target_date.isoformat()
        if cache_key in self._series_cache:
            return self._series_cache[cache_key]
        aggregated = {}
        series_end = _period_end("seasonal", target_date)
        predictions = (
            UssdMarketPrediction.objects.select_related("market")
            .filter(
                commodity__in=self._supported_commodities(),
                pricetype=RETAIL_PRICE_TYPE,
                period=UssdMarketPrediction.Period.DAILY,
                target_date__gte=target_date,
                target_date__lte=series_end,
            )
            .order_by("commodity", "target_date", "market__name")
        )
        commodity_date_totals: dict[str, dict[str, list[Decimal]]] = {}
        commodity_meta: dict[str, dict] = {}
        for prediction in predictions:
            date_key = prediction.target_date.isoformat()
            commodity_date_totals.setdefault(prediction.commodity, {}).setdefault(date_key, []).append(
                _normalize_to_kg(prediction)
            )
            commodity_meta.setdefault(
                prediction.commodity,
                {
                    "currency": prediction.currency,
                    "season": prediction.season,
                },
            )

        for commodity, date_map in commodity_date_totals.items():
            aggregated[commodity] = {
                "currency": commodity_meta[commodity]["currency"],
                "season": commodity_meta[commodity]["season"],
                "predictions": {
                    date_key: sum(values) / Decimal(len(values))
                    for date_key, values in date_map.items()
                },
            }

        self._series_cache[cache_key] = aggregated
        return aggregated

    def _average_by_market(self, predictions: list[UssdMarketPrediction], period: str) -> dict[str, dict]:
        aggregates: dict[int, list[Decimal]] = {}
        market_meta: dict[int, dict] = {}
        for prediction in predictions:
            if prediction.period != period or prediction.pricetype != RETAIL_PRICE_TYPE:
                continue
            normalized = _normalize_to_kg(prediction)
            aggregates.setdefault(prediction.market_id, []).append(normalized)
            market_meta.setdefault(
                prediction.market_id,
                {
                    "market": prediction.market,
                    "currency": prediction.currency,
                    "season": prediction.season,
                },
            )
        return {
            market_id: {
                "price": sum(values) / Decimal(len(values)),
                **market_meta[market_id],
            }
            for market_id, values in aggregates.items()
        }

    def _window_items(self, series_map: dict[str, Decimal], start_date, end_date):
        return [
            (date_key, price)
            for date_key, price in sorted(series_map.items())
            if start_date.isoformat() <= date_key <= end_date.isoformat()
        ]

    def _select_period_for_date(self, selected_date, candidate_date):
        week_end = _period_end("weekly", selected_date)
        month_end = _period_end("monthly", selected_date)
        if candidate_date == selected_date:
            return "daily"
        if candidate_date <= week_end:
            return "weekly"
        if candidate_date <= month_end:
            return "monthly"
        return "seasonal"

    def _candidate_windows(self, series_map: dict[str, Decimal], target_date) -> list[dict]:
        import pandas as pd

        season_end = _period_end("seasonal", target_date)
        windows = []

        week_start = target_date
        while week_start <= season_end:
            week_end = min(calendar_week_end_date(pd.Timestamp(week_start)).date(), season_end)
            items = self._window_items(series_map, week_start, week_end)
            if items:
                windows.append(
                    {
                        "period": UssdMarketRecommendation.Period.WEEKLY,
                        "start": week_start,
                        "end": week_end,
                        "average": _average_prices(items),
                    }
                )
            week_start = week_end + timedelta(days=1)

        month_start = target_date
        while month_start <= season_end:
            month_end = min((pd.Timestamp(month_start) + pd.offsets.MonthEnd(0)).date(), season_end)
            items = self._window_items(series_map, month_start, month_end)
            if items:
                windows.append(
                    {
                        "period": UssdMarketRecommendation.Period.MONTHLY,
                        "start": month_start,
                        "end": month_end,
                        "average": _average_prices(items),
                    }
                )
            month_start = month_end + timedelta(days=1)

        return windows

    def _is_favorable_price(
        self,
        action: str,
        value: Decimal,
        lowest: Decimal,
        highest: Decimal,
    ) -> bool:
        position = _price_position(value, lowest, highest)
        if action == UssdMarketRecommendation.Action.BUY:
            return position <= LOW_PRICE_POSITION
        return position >= HIGH_PRICE_POSITION

    def _continuous_window_end(
        self,
        action: str,
        items,
        start_index: int,
        lowest: Decimal,
        highest: Decimal,
    ):
        from datetime import date

        last_date = date.fromisoformat(items[start_index][0])
        for date_key, price in items[start_index:]:
            if not self._is_favorable_price(action, price, lowest, highest):
                break
            last_date = date.fromisoformat(date_key)
        return last_date

    def _time_recommendation(self, role: str, commodity: str, target_date):
        from datetime import date

        series_bundle = self._load_retail_series(target_date).get(commodity)
        if not series_bundle:
            raise LookupError("Prediction data not available.")

        series_map = series_bundle["predictions"]
        today_key = target_date.isoformat()
        today_price = series_map.get(today_key)
        if today_price is None:
            raise LookupError("Today's prediction is not available.")

        action = self.ROLE_CONFIG[role]
        weekly_items = self._window_items(series_map, target_date, _period_end("weekly", target_date))
        seasonal_items = self._window_items(series_map, target_date, _period_end("seasonal", target_date))
        if not seasonal_items:
            raise LookupError("Prediction window is not available.")

        lowest_value = min(price for _date_key, price in seasonal_items)
        highest_value = max(price for _date_key, price in seasonal_items)
        spread_pct = _range_spread_pct(lowest_value, highest_value)
        candidate_windows = self._candidate_windows(series_map, target_date)
        if not candidate_windows:
            raise LookupError("Prediction windows are not available.")

        weekly_average = sum(price for _date_key, price in weekly_items) / Decimal(len(weekly_items))
        trend = _trend_from_change(_percent_change(weekly_average, today_price))

        chooser = min if action == UssdMarketRecommendation.Action.BUY else max
        best_window = chooser(candidate_windows, key=lambda window: window["average"])
        current_window = next(
            (
                window
                for window in candidate_windows
                if window["period"] == UssdMarketRecommendation.Period.WEEKLY
                and window["start"] == target_date
            ),
            candidate_windows[0],
        )
        best_period = best_window["period"]
        best_date = best_window["start"]
        best_window_end = best_window["end"]
        best_value = best_window["average"]
        best_window_label = _format_window(best_date, best_window_end)
        current_value = current_window["average"]
        if action == UssdMarketRecommendation.Action.BUY:
            improvement_pct = max(
                Decimal("0.00"),
                ((current_value - best_value) / current_value) * Decimal("100")
                if current_value
                else Decimal("0.00"),
            )
            action_word = "buy"
            direction = "lower"
        else:
            improvement_pct = max(
                Decimal("0.00"),
                ((best_value - current_value) / current_value) * Decimal("100")
                if current_value
                else Decimal("0.00"),
            )
            action_word = "sell"
            direction = "higher"

        best_window_is_now = best_date <= target_date <= best_window_end
        prices_are_stable = spread_pct < MIN_MEANINGFUL_SPREAD or improvement_pct < WAIT_THRESHOLD

        if best_window_is_now:
            confidence = _round_confidence(Decimal("82.00") + min(Decimal("10.00"), improvement_pct))
            summary = f"Best time to {action_word} is now."
            reason = f"The current window is favorable for {action_word}ing during {series_bundle['season']}."
        elif prices_are_stable:
            confidence = _round_confidence(Decimal("70.00") + spread_pct)
            summary = f"Prices are stable; best time to {action_word} is {best_window_label}."
            reason = (
                f"The predicted movement is small, so the timing advantage is low. "
                f"If you can choose, use this window during {series_bundle['season']}."
            )
        else:
            confidence = _round_confidence(Decimal("78.00") + min(Decimal("12.00"), improvement_pct))
            summary = f"Wait to {action_word}; best time is {best_window_label}."
            reason = (
                f"The best {action_word} window is later, when the model expects {direction} prices "
                f"during {series_bundle['season']}."
            )
        return {
            "recommendation_type": UssdMarketRecommendation.RecommendationType.TIME,
            "action": action,
            "period": best_period,
            "window_start": best_date,
            "window_end": best_window_end,
            "market": None,
            "season": series_bundle["season"],
            "trend": trend,
            "recommended_price": _round_money(best_value),
            "currency": series_bundle["currency"],
            "confidence": confidence,
            "summary": summary,
            "reason": reason,
        }

    def _market_recommendation(self, role: str, commodity: str, predictions: list[UssdMarketPrediction], target_date):
        market_averages = self._average_by_market(predictions, "daily")
        weekly_averages = self._average_by_market(predictions, "weekly")
        if not market_averages:
            raise LookupError("Daily market prediction data not available.")

        action = self.ROLE_CONFIG[role]
        chooser = min if action == UssdMarketRecommendation.Action.BUY else max
        best_market_id = chooser(
            market_averages,
            key=lambda market_id: market_averages[market_id]["price"],
        )
        best_data = market_averages[best_market_id]
        sorted_prices = sorted(data["price"] for data in market_averages.values())
        if action == UssdMarketRecommendation.Action.SELL:
            edge = best_data["price"] - sorted_prices[-2] if len(sorted_prices) > 1 else Decimal("0.00")
        else:
            edge = sorted_prices[1] - best_data["price"] if len(sorted_prices) > 1 else Decimal("0.00")
        baseline = best_data["price"] if best_data["price"] else Decimal("1.00")
        edge_pct = abs(_percent_change(edge + baseline, baseline))
        weekly_price = weekly_averages.get(best_market_id, best_data)["price"]
        trend_change = _percent_change(weekly_price, best_data["price"])
        trend = _trend_from_change(trend_change)
        confidence = _round_confidence(Decimal("68.00") + min(Decimal("22.00"), edge_pct))

        if action == UssdMarketRecommendation.Action.BUY:
            summary = f"Best market to buy is {best_data['market'].name}."
            reason = (
                f"This market has the lowest predicted price today. Weekly trend is {trend}."
            )
        else:
            summary = f"Best market to sell is {best_data['market'].name}."
            reason = (
                f"This market has the highest predicted price today. Weekly trend is {trend}."
            )

        return {
            "recommendation_type": UssdMarketRecommendation.RecommendationType.MARKET,
            "action": action,
            "period": UssdMarketRecommendation.Period.DAILY,
            "window_start": target_date,
            "window_end": target_date,
            "market": best_data["market"],
            "season": best_data["season"],
            "trend": trend,
            "recommended_price": _round_money(best_data["price"]),
            "currency": best_data["currency"],
            "confidence": confidence,
            "summary": summary,
            "reason": reason,
        }

    def refresh_for_date(self, target_date=None, stdout=None, progress_callback=None):
        selected_date = target_date or timezone.localdate()
        predictions_by_commodity = self._load_predictions(selected_date)
        results = []
        failures = []
        commodities = self._supported_commodities()
        roles = list(self.ROLE_CONFIG.keys())

        for role in roles:
            for commodity in commodities:
                if progress_callback is not None:
                    progress_callback(
                        {
                            "status": "started",
                            "role": role,
                            "commodity": commodity,
                            "current": 0,
                            "total": 1,
                            "message": "Building recommendation set.",
                        }
                    )

                commodity_predictions = predictions_by_commodity.get(commodity, [])
                if not commodity_predictions:
                    failure = {
                        "role": role,
                        "commodity": commodity,
                        "error": "Prediction data not available.",
                    }
                    failures.append(failure)
                    if stdout is not None:
                        stdout.write(f"SKIPPED | {role} | {commodity} | Prediction data not available.")
                    if progress_callback is not None:
                        progress_callback(
                            {
                                "status": "skipped",
                                "role": role,
                                "commodity": commodity,
                                "current": 1,
                                "total": 1,
                                "message": failure["error"],
                            }
                        )
                    continue

                try:
                    payloads = (
                        self._time_recommendation(role, commodity, selected_date),
                        self._market_recommendation(role, commodity, commodity_predictions, selected_date),
                    )
                    for payload in payloads:
                        recommendation, _created = UssdMarketRecommendation.objects.update_or_create(
                            role=role,
                            commodity=commodity,
                            recommendation_type=payload["recommendation_type"],
                            target_date=selected_date,
                            defaults=payload,
                        )
                        results.append(recommendation)
                        if stdout is not None:
                            stdout.write(
                                (
                                    f"{selected_date} | {role} | {commodity} | "
                                    f"{recommendation.recommendation_type} | {recommendation.summary}"
                                )
                            )
                except LookupError as exc:
                    failure = {"role": role, "commodity": commodity, "error": str(exc)}
                    failures.append(failure)
                    if stdout is not None:
                        stdout.write(f"SKIPPED | {role} | {commodity} | {exc}")
                    if progress_callback is not None:
                        progress_callback(
                            {
                                "status": "skipped",
                                "role": role,
                                "commodity": commodity,
                                "current": 1,
                                "total": 1,
                                "message": str(exc),
                            }
                        )
                    continue

                if progress_callback is not None:
                    progress_callback(
                        {
                            "status": "completed",
                            "role": role,
                            "commodity": commodity,
                            "current": 1,
                            "total": 1,
                            "message": "Recommendation set ready.",
                        }
                    )

        return {"results": results, "failures": failures}


def get_recommendation_service() -> RecommendationRefreshService:
    return RecommendationRefreshService(get_forecast_service())
