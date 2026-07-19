from decimal import Decimal, InvalidOperation

from django.contrib.auth import get_user_model
from django.http import HttpResponse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from apps.auth.models import Profile

from .forecasting import (
    ForecastUnavailable,
    PERIOD_MAP as FORECAST_PERIOD_MAP,
    PRICE_TYPE_MAP,
    calendar_week_end_date,
    get_forecast_service,
    season_end_date,
)
from .models import UssdPriceAlert, UssdSubscriber
from .prediction_cache import get_cached_prediction
from .recommendations import get_cached_recommendation
from .weather import (
    WeatherForecastUnavailable,
    get_weather_region_options,
    get_weather_service,
)

User = get_user_model()


ROLE_MAP = {
    "1": UssdSubscriber.Role.FARMER,
    "2": UssdSubscriber.Role.ENTREPRENEUR,
    "3": UssdSubscriber.Role.BUYER,
}

COMMODITY_MAP = {
    "1": ("maize", "Maize"),
    "2": ("rice", "Rice"),
}

MARKET_PRICE_DATA = {
    ("1", "1"): "END Maize at Ifakara Central: Current TZS 820/kg, Yesterday TZS 790/kg, Trend: Rising.",
    ("1", "2"): "END Maize in Nearby Markets: Current TZS 780/kg, Yesterday TZS 800/kg, Trend: Slightly Down.",
    ("2", "1"): "END Rice at Ifakara Central: Current TZS 2,150/kg, Yesterday TZS 2,120/kg, Trend: Rising.",
    ("2", "2"): "END Rice in Nearby Markets: Current TZS 2,080/kg, Yesterday TZS 2,060/kg, Trend: Stable Upward.",
}

@method_decorator(csrf_exempt, name="dispatch")
class UssdMenuView(View):
    http_method_names = ["get", "post"]

    def _get_value(self, request, key):
        return (
            request.POST.get(key)
            or request.GET.get(key)
            or request.headers.get(key)
            or request.headers.get(key.lower())
            or ""
        ).strip()

    def _normalize_segments(self, text):
        if not text:
            return []
        if text.strip() == "0":
            return ["0"]

        normalized = []
        for segment in text.split("*"):
            value = segment.strip()
            if not value:
                continue
            if value == "0":
                if normalized:
                    normalized.pop()
                continue
            normalized.append(value)
        return normalized

    def _main_menu(self):
        return (
            "CON Main Menu\n"
            "1. Market Prices\n"
            "2. Price Prediction\n"
            "3. My Recommendations\n"
            "4. Weather Forecast\n"
            "5. My Account\n"
            "0. Exit"
        )

    def _is_exit(self, segments):
        return segments == ["0"]

    def _strip_completed_registration_segments(self, subscriber, segments):
        if len(segments) < 3:
            return segments
        selected_role = ROLE_MAP.get(segments[1])
        if segments[0] == subscriber.full_name and selected_role == subscriber.role:
            return segments[2:]
        return segments

    def _forecast_market_options(self):
        return get_forecast_service().get_market_options()

    def _forecast_commodity_options(self):
        return get_forecast_service().get_commodity_options()

    def _recommendation_prompt_lines(self, subscriber):
        if subscriber.role == UssdSubscriber.Role.BUYER:
            return (
                "CON Select need\n"
                "1. Best Time to Buy\n"
                "2. Best Market to Buy\n"
                "0. Back"
            )
        return (
            "CON Select need\n"
            "1. Best Time to Sell\n"
            "2. Best Market to Sell\n"
            "0. Back"
        )

    def _recommendation_window_end(self, recommendation):
        import pandas as pd

        target = pd.Timestamp(recommendation.target_date).normalize()
        if recommendation.period == "daily":
            return recommendation.target_date.isoformat()
        if recommendation.period == "weekly":
            return calendar_week_end_date(target).date().isoformat()
        if recommendation.period == "monthly":
            return (target + pd.offsets.MonthEnd(0)).date().isoformat()
        if recommendation.period == "seasonal":
            return season_end_date(target).date().isoformat()
        return recommendation.target_date.isoformat()

    def _split_name(self, full_name):
        name_parts = full_name.split()
        if not name_parts:
            return "USSD", "User"
        first_name = name_parts[0]
        last_name = " ".join(name_parts[1:])
        return first_name, last_name

    def _sync_backend_profile(self, phone_number, full_name, role):
        profile = Profile.objects.select_related("user").filter(phone_number=phone_number).first()
        first_name, last_name = self._split_name(full_name)

        if profile is None:
            user = User(username=phone_number, first_name=first_name, last_name=last_name)
            user.set_unusable_password()
            user.save()
            profile = Profile.objects.create(
                user=user,
                role=role,
                phone_number=phone_number,
                email_verified_at=timezone.now(),
            )
            return user, profile

        user = profile.user
        user.username = phone_number
        user.first_name = first_name
        user.last_name = last_name
        user.save(update_fields=["username", "first_name", "last_name"])

        update_fields = ["role", "phone_number", "updated_at"]
        profile.role = role
        profile.phone_number = phone_number
        profile.save(update_fields=update_fields)
        return user, profile

    def _handle_registration(self, phone_number, segments):
        if not segments:
            return "CON Welcome to SmartMarket DSS.\nEnter your full name"

        full_name = segments[0]
        if len(segments) == 1:
            return (
                "CON Select your role\n"
                "1. Farmer\n"
                "2. Entrepreneur\n"
                "3. Buyer\n"
                "0. Back"
            )

        role = ROLE_MAP.get(segments[1])
        if role is None:
            return "END Invalid role selection."

        user, _profile = self._sync_backend_profile(phone_number or "unknown", full_name, role)
        UssdSubscriber.objects.update_or_create(
            phone_number=phone_number or "unknown",
            defaults={"user": user, "full_name": full_name, "role": role},
        )
        return self._main_menu()

    def _handle_market_prices(self, segments):
        if len(segments) == 1:
            return "CON Select commodity\n1. Maize\n2. Rice\n0. Back"
        if len(segments) == 2:
            if segments[1] not in COMMODITY_MAP:
                return "END Invalid commodity selection."
            return "CON Select market\n1. Ifakara Central\n2. Nearby Markets\n0. Back"
        if len(segments) == 3:
            return MARKET_PRICE_DATA.get(
                (segments[1], segments[2]),
                "END Invalid market selection.",
            )
        return "END Invalid choice."

    def _handle_prediction(self, segments):
        if len(segments) == 1:
            market_lines = [f"{option}. {name}" for option, name in self._forecast_market_options()]
            return (
                "CON Select market\n"
                + "\n".join(market_lines)
                + "\n0. Back"
            )
        if len(segments) == 2:
            market_lookup = dict(self._forecast_market_options())
            if segments[1] not in market_lookup:
                return "END Invalid market selection."
            commodity_lines = [f"{option}. {name}" for option, name in self._forecast_commodity_options()]
            return (
                "CON Select commodity\n"
                + "\n".join(commodity_lines)
                + "\n0. Back"
            )
        if len(segments) == 3:
            if segments[2] not in dict(self._forecast_commodity_options()):
                return "END Invalid commodity selection."
            return "CON Select price type\n1. Retail\n2. Wholesale\n0. Back"
        if len(segments) == 4:
            if segments[3] not in PRICE_TYPE_MAP:
                return "END Invalid price type."
            return (
                "CON Select period\n"
                "1. Daily\n"
                "2. Weekly\n"
                "3. Monthly\n"
                "4. Seasonal\n"
                "0. Back"
            )
        if len(segments) == 5:
            market = dict(self._forecast_market_options()).get(segments[1])
            commodity = dict(self._forecast_commodity_options()).get(segments[2])
            price_type = PRICE_TYPE_MAP.get(segments[3])
            period = FORECAST_PERIOD_MAP.get(segments[4])
            if market is None:
                return "END Invalid market selection."
            if commodity is None:
                return "END Invalid commodity selection."
            if price_type is None:
                return "END Invalid price type."
            if period is None:
                return "END Invalid period selection."

            try:
                result = get_cached_prediction(
                    market=market,
                    commodity=commodity,
                    pricetype=price_type[0],
                    period=period,
                )
            except ForecastUnavailable:
                return "END Prediction not available right now."

            period_label = {
                "daily": f"Day: {result.target_date.isoformat()}",
                "weekly": f"Week: {result.target_date.isoformat()} to {result.period_end.isoformat()}",
                "monthly": f"Month: {result.target_date.isoformat()} to {result.period_end.isoformat()}",
                "seasonal": (
                    f"Season: {result.season} "
                    f"({result.target_date.isoformat()} to {result.period_end.isoformat()})"
                ),
            }[result.period]
            return (
                "END Predicted Price\n"
                f"Market: {result.market.name}\n"
                f"Commodity: {result.commodity}\n"
                f"Type: {result.pricetype} ({result.unit})\n"
                f"{period_label}\n"
                f"Price: {result.currency} {result.predicted_price:,.2f}"
            )
        return "END Invalid choice."

    def _handle_recommendations(self, subscriber, segments):
        if len(segments) == 1:
            commodity_lines = [f"{option}. {name}" for option, name in self._forecast_commodity_options()]
            return (
                "CON Select commodity\n"
                + "\n".join(commodity_lines)
                + "\n0. Back"
            )
        if len(segments) == 2:
            if segments[1] not in dict(self._forecast_commodity_options()):
                return "END Invalid commodity selection."
            return self._recommendation_prompt_lines(subscriber)
        if len(segments) == 3:
            commodity = dict(self._forecast_commodity_options()).get(segments[1])
            recommendation_type = {
                "1": "time",
                "2": "market",
            }.get(segments[2])
            if commodity is None:
                return "END Invalid commodity selection."
            if recommendation_type is None:
                return "END Invalid recommendation option."

            try:
                recommendation = get_cached_recommendation(
                    role=subscriber.role,
                    commodity=commodity,
                    recommendation_type=recommendation_type,
                )
            except LookupError:
                return "END Recommendation not available right now."

            if recommendation.recommendation_type == "time":
                period_label = {
                    "daily": "today",
                    "weekly": "week",
                    "monthly": "month",
                    "seasonal": "season",
                }.get(recommendation.period, recommendation.period)
                return (
                    "END Recommendation\n"
                    f"{recommendation.summary}\n"
                    f"Window: {period_label}\n"
                    f"Season: {recommendation.season}\n"
                    f"Trend: {recommendation.trend}\n"
                    f"Reason: {recommendation.reason}"
                )
            return (
                "END Recommendation\n"
                f"{recommendation.summary}\n"
                f"Trend: {recommendation.trend}\n"
                f"Reason: {recommendation.reason}"
            )
        return "END Invalid choice."

    def _handle_weather_forecast(self, segments):
        region_options = get_weather_region_options()
        if len(segments) == 1:
            region_lines = [f"{option}. {region.name}" for option, region in region_options]
            return "CON Select region\n" + "\n".join(region_lines) + "\n0. Back"

        if len(segments) == 2:
            region = dict(region_options).get(segments[1])
            if region is None:
                return "END Invalid region selection."
            try:
                forecast = get_weather_service().fetch_weekly_forecast(region)
            except WeatherForecastUnavailable:
                return "END Weather forecast not available right now."

            day_lines = [
                (
                    f"{day['weekday']}: {day['condition']}, "
                    f"{day['guidance']}, {day['temperature']}"
                )
                for day in forecast["days"]
            ]
            return (
                "END Weather Forecast\n"
                f"Region: {forecast['region']}\n"
                f"Season: {forecast['season']}\n"
                + "\n".join(day_lines)
            )
        return "END Invalid choice."

    def _profile_for_subscriber(self, subscriber):
        if subscriber.user_id:
            profile, _created = Profile.objects.get_or_create(
                user=subscriber.user,
                defaults={
                    "role": subscriber.role,
                    "phone_number": subscriber.phone_number,
                },
            )
            profile_needs_update = False
            if profile.role != subscriber.role:
                profile.role = subscriber.role
                profile_needs_update = True
            if not profile.phone_number:
                profile.phone_number = subscriber.phone_number
                profile_needs_update = True
            if profile_needs_update:
                profile.save(update_fields=["role", "phone_number", "updated_at"])
            return profile

        user, profile = self._sync_backend_profile(
            subscriber.phone_number,
            subscriber.full_name,
            subscriber.role,
        )
        subscriber.user = user
        subscriber.save(update_fields=["user"])
        return profile

    def _account_menu(self, subscriber):
        if subscriber.role == UssdSubscriber.Role.FARMER:
            return (
                "CON My Account\n"
                "1. View Profile\n"
                "2. Change Role\n"
                "3. Set Price Alert\n"
                "4. Update Farm Location\n"
                "5. Update Farm Group\n"
                "0. Back"
            )
        return (
            "CON My Account\n"
            "1. View Profile\n"
            "2. Change Role\n"
            "3. Set Price Alert\n"
            "0. Back"
        )

    def _view_profile_response(self, subscriber, profile):
        saved_alerts = {
            alert.commodity: alert.target_price
            for alert in subscriber.price_alerts.filter(is_active=True)
        }
        maize_alert = saved_alerts.get(UssdPriceAlert.Commodity.MAIZE)
        rice_alert = saved_alerts.get(UssdPriceAlert.Commodity.RICE)
        message = (
            f"END Name: {subscriber.full_name}, Role: {subscriber.get_role_display()}, "
            f"Phone: {subscriber.phone_number}"
        )
        if subscriber.role == UssdSubscriber.Role.FARMER:
            farm_location = profile.farm_location or "Not set"
            farm_group = profile.farm_group or "Not set"
            message += f", Farm Location: {farm_location}, Farm Group: {farm_group}"
        maize_alert_text = f"TZS {maize_alert:.2f}" if maize_alert is not None else "Not set"
        rice_alert_text = f"TZS {rice_alert:.2f}" if rice_alert is not None else "Not set"
        message += f", Maize Alert: {maize_alert_text}, Rice Alert: {rice_alert_text}"
        return message

    def _handle_account(self, subscriber, segments):
        profile = self._profile_for_subscriber(subscriber)

        if len(segments) == 1:
            return self._account_menu(subscriber)

        if len(segments) == 2:
            if segments[1] == "1":
                return self._view_profile_response(subscriber, profile)
            if segments[1] == "2":
                return "CON Change role\n1. Farmer\n2. Entrepreneur\n3. Buyer\n0. Back"
            if segments[1] == "3":
                return "CON Select commodity alert\n1. Maize\n2. Rice\n0. Back"
            if segments[1] == "4" and subscriber.role == UssdSubscriber.Role.FARMER:
                return "CON Enter farm location"
            if segments[1] == "5" and subscriber.role == UssdSubscriber.Role.FARMER:
                return "CON Enter farm group"
            return "END Invalid account option."

        if len(segments) == 3:
            if segments[1] == "2":
                role = ROLE_MAP.get(segments[2])
                if role is None:
                    return "END Invalid role selection."
                subscriber.role = role
                subscriber.save(update_fields=["role", "updated_at"])
                profile.role = role
                profile.save(update_fields=["role", "updated_at"])
                return f"END Role updated to {subscriber.get_role_display()}."
            if segments[1] == "3":
                if segments[2] not in COMMODITY_MAP:
                    return "END Invalid commodity selection."
                commodity_name = COMMODITY_MAP[segments[2]][1]
                return f"CON Enter target price for {commodity_name}"
            if segments[1] == "4" and subscriber.role == UssdSubscriber.Role.FARMER:
                profile.farm_location = segments[2]
                profile.save(update_fields=["farm_location", "updated_at"])
                return f"END Farm location updated to {profile.farm_location}."
            if segments[1] == "5" and subscriber.role == UssdSubscriber.Role.FARMER:
                profile.farm_group = segments[2]
                profile.save(update_fields=["farm_group", "updated_at"])
                return f"END Farm group updated to {profile.farm_group}."
            return "END Invalid account option."

        if len(segments) == 4 and segments[1] == "3":
            commodity = COMMODITY_MAP.get(segments[2])
            if commodity is None:
                return "END Invalid commodity selection."
            try:
                target_price = Decimal(segments[3])
            except InvalidOperation:
                return "END Invalid price. Enter a numeric target price."
            UssdPriceAlert.objects.update_or_create(
                subscriber=subscriber,
                commodity=commodity[0],
                defaults={"target_price": target_price, "is_active": True},
            )
            return (
                f"END Price alert saved for {commodity[1]} at TZS {target_price:.2f}. "
                "You will be notified by SMS when the price is reached."
            )
        return "END Invalid choice."

    def post(self, request, *args, **kwargs):
        session_id = self._get_value(request, "sessionId")
        service_code = self._get_value(request, "serviceCode")
        phone_number = self._get_value(request, "phoneNumber")
        text = self._get_value(request, "text")

        _ = session_id, service_code, phone_number
        segments = self._normalize_segments(text)
        subscriber = UssdSubscriber.objects.select_related("user").filter(phone_number=phone_number).first()
        if subscriber is not None:
            segments = self._strip_completed_registration_segments(subscriber, segments)

        if self._is_exit(segments):
            response_text = "END Thank you for using SmartMarket DSS. Asante! Kwa heri."
        elif subscriber is None:
            response_text = self._handle_registration(phone_number, segments)
        elif not segments:
            response_text = self._main_menu()
        elif segments[0] == "1":
            response_text = self._handle_market_prices(segments)
        elif segments[0] == "2":
            response_text = self._handle_prediction(segments)
        elif segments[0] == "3":
            response_text = self._handle_recommendations(subscriber, segments)
        elif segments[0] == "4":
            response_text = self._handle_weather_forecast(segments)
        elif segments[0] == "5":
            response_text = self._handle_account(subscriber, segments)
        else:
            response_text = "END Invalid choice. Please try again."

        return HttpResponse(response_text, content_type="text/plain")

    def get(self, request, *args, **kwargs):
        return self.post(request, *args, **kwargs)
