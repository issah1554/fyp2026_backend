from decimal import Decimal, InvalidOperation

from django.contrib.auth import get_user_model
from django.http import HttpResponse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from apps.auth.models import Profile
from apps.users.models import Role

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
from .market_prices_api import (
    LiveMarketPricesUnavailable,
    get_market_price_service,
)
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

LANGUAGE_MAP = {
    "1": UssdSubscriber.Language.ENGLISH,
    "2": UssdSubscriber.Language.SWAHILI,
}

LANGUAGE_LABELS = {
    UssdSubscriber.Language.ENGLISH: "English",
    UssdSubscriber.Language.SWAHILI: "Kiswahili",
}

TRANSLATIONS = {
    UssdSubscriber.Language.ENGLISH: {
        "select_language": "CON Select language\n1. English\n2. Kiswahili\n0. Exit",
        "invalid_language": "END Invalid language selection.",
        "welcome_name": "CON Welcome to SmartMarket DSS.\nEnter your full name",
        "select_role": "CON Select your role\n1. Farmer\n2. Entrepreneur\n3. Buyer\n0. Back",
        "invalid_role": "END Invalid role selection.",
        "main_menu": (
            "CON Main Menu\n"
            "1. Market Prices\n"
            "2. Price Prediction\n"
            "3. My Recommendations\n"
            "4. Weather Forecast\n"
            "5. My Account\n"
            "0. Exit"
        ),
        "recommendation_need_buy": "CON Select need\n1. Best Time to Buy\n2. Best Market to Buy\n0. Back",
        "recommendation_need_sell": "CON Select need\n1. Best Time to Sell\n2. Best Market to Sell\n0. Back",
        "goodbye": "END Thank you for using SmartMarket DSS. Asante! Kwa heri.",
        "invalid_choice": "END Invalid choice. Please try again.",
        "invalid_account_option": "END Invalid account option.",
    },
    UssdSubscriber.Language.SWAHILI: {
        "select_language": "CON Chagua lugha\n1. English\n2. Kiswahili\n0. Toka",
        "invalid_language": "END Chaguo la lugha si sahihi.",
        "welcome_name": "CON Karibu SmartMarket DSS.\nWeka majina yako kamili",
        "select_role": "CON Chagua jukumu lako\n1. Mkulima\n2. Mjasiriamali\n3. Mnunuzi\n0. Rudi",
        "invalid_role": "END Chaguo la jukumu si sahihi.",
        "main_menu": (
            "CON Menyu Kuu\n"
            "1. Bei za Sokoni\n"
            "2. Utabiri wa Bei\n"
            "3. Mapendekezo Yangu\n"
            "4. Utabiri wa Hali ya Hewa\n"
            "5. Akaunti Yangu\n"
            "0. Toka"
        ),
        "recommendation_need_buy": "CON Chagua unachohitaji\n1. Muda Bora wa Kununua\n2. Soko Bora la Kununua\n0. Rudi",
        "recommendation_need_sell": "CON Chagua unachohitaji\n1. Muda Bora wa Kuuza\n2. Soko Bora la Kuuza\n0. Rudi",
        "goodbye": "END Asante kwa kutumia SmartMarket DSS. Kwa heri.",
        "invalid_choice": "END Chaguo si sahihi. Tafadhali jaribu tena.",
        "invalid_account_option": "END Chaguo la akaunti si sahihi.",
    },
}

@method_decorator(csrf_exempt, name="dispatch")
class UssdMenuView(View):
    http_method_names = ["get", "post"]

    def _resolve_profile_role(self, role_code):
        try:
            role_label = Profile.Role(role_code).label
        except ValueError:
            role_label = role_code.replace("_", " ").title()
        role, _created = Role.objects.get_or_create(
            code=role_code,
            defaults={
                "name": role_label,
                "description": f"{role_label} role.",
                "is_system": True,
            },
        )
        return role

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

    def _text(self, language, key):
        return TRANSLATIONS.get(language, TRANSLATIONS[UssdSubscriber.Language.ENGLISH])[key]

    def _translate_role(self, role, language):
        labels = {
            UssdSubscriber.Role.FARMER: {
                UssdSubscriber.Language.ENGLISH: "Farmer",
                UssdSubscriber.Language.SWAHILI: "Mkulima",
            },
            UssdSubscriber.Role.ENTREPRENEUR: {
                UssdSubscriber.Language.ENGLISH: "Entrepreneur",
                UssdSubscriber.Language.SWAHILI: "Mjasiriamali",
            },
            UssdSubscriber.Role.BUYER: {
                UssdSubscriber.Language.ENGLISH: "Buyer",
                UssdSubscriber.Language.SWAHILI: "Mnunuzi",
            },
        }
        return labels.get(role, {}).get(language, role)

    def _translate_commodity(self, commodity, language):
        labels = {
            "Beans": {UssdSubscriber.Language.ENGLISH: "Beans", UssdSubscriber.Language.SWAHILI: "Maharage"},
            "Rice": {UssdSubscriber.Language.ENGLISH: "Rice", UssdSubscriber.Language.SWAHILI: "Mchele"},
            "maize": {UssdSubscriber.Language.ENGLISH: "Maize", UssdSubscriber.Language.SWAHILI: "Mahindi"},
            "rice": {UssdSubscriber.Language.ENGLISH: "Rice", UssdSubscriber.Language.SWAHILI: "Mchele"},
            "Maize": {UssdSubscriber.Language.ENGLISH: "Maize", UssdSubscriber.Language.SWAHILI: "Mahindi"},
        }
        return labels.get(commodity, {}).get(language, commodity)

    def _translate_price_type(self, price_type, language):
        labels = {
            "Retail": {UssdSubscriber.Language.ENGLISH: "Retail", UssdSubscriber.Language.SWAHILI: "Rejareja"},
            "Wholesale": {UssdSubscriber.Language.ENGLISH: "Wholesale", UssdSubscriber.Language.SWAHILI: "Jumla"},
        }
        return labels.get(price_type, {}).get(language, price_type)

    def _translate_trend(self, trend, language):
        labels = {
            "rising": {UssdSubscriber.Language.ENGLISH: "rising", UssdSubscriber.Language.SWAHILI: "inapanda"},
            "falling": {UssdSubscriber.Language.ENGLISH: "falling", UssdSubscriber.Language.SWAHILI: "inashuka"},
            "stable": {UssdSubscriber.Language.ENGLISH: "stable", UssdSubscriber.Language.SWAHILI: "imetulia"},
        }
        return labels.get(trend, {}).get(language, trend)

    def _translate_day(self, weekday, language):
        labels = {
            "Monday": "Jumatatu",
            "Tuesday": "Jumanne",
            "Wednesday": "Jumatano",
            "Thursday": "Alhamisi",
            "Friday": "Ijumaa",
            "Saturday": "Jumamosi",
            "Sunday": "Jumapili",
        }
        if language == UssdSubscriber.Language.SWAHILI:
            return labels.get(weekday, weekday)
        return weekday

    def _translate_weather_condition(self, condition, language):
        labels = {
            "Sunny": "Jua",
            "Partly cloudy": "Kuna mawingu kiasi",
            "Cloudy": "Mawingu",
            "Foggy": "Ukungu",
            "Drizzle": "Manyunyu",
            "Rainy": "Mvua",
            "Very cold": "Baridi kali",
            "Showers": "Vipindi vya mvua",
            "Thunderstorms": "Ngurumo za radi",
            "Mixed weather": "Hali ya hewa mchanganyiko",
        }
        if language == UssdSubscriber.Language.SWAHILI:
            return labels.get(condition, condition)
        return condition

    def _translate_weather_guidance(self, guidance, language):
        labels = {
            "rain likely": "mvua inatarajiwa",
            "possible rain": "mvua inawezekana",
            "low rain": "uwezekano mdogo wa mvua",
            "temp unavailable": "joto halijapatikana",
        }
        if language == UssdSubscriber.Language.SWAHILI:
            return labels.get(guidance, guidance)
        return guidance

    def _main_menu(self, language):
        return self._text(language, "main_menu")

    def _is_exit(self, segments):
        return segments == ["0"]

    def _strip_completed_registration_segments(self, subscriber, segments):
        if len(segments) >= 4:
            selected_language = LANGUAGE_MAP.get(segments[0])
            selected_role = ROLE_MAP.get(segments[2])
            if (
                selected_language == subscriber.preferred_language
                and segments[1] == subscriber.full_name
                and selected_role == subscriber.role
            ):
                return segments[3:]
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

    def _recommendation_prompt_lines(self, subscriber, language):
        if subscriber.role == UssdSubscriber.Role.BUYER:
            return self._text(language, "recommendation_need_buy")
        return self._text(language, "recommendation_need_sell")

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
        profile_role = self._resolve_profile_role(role)

        if profile is None:
            user = User(username=phone_number, first_name=first_name, last_name=last_name)
            user.set_unusable_password()
            user.save()
            profile = Profile.objects.create(
                user=user,
                role=profile_role,
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
        profile.role = profile_role
        profile.phone_number = phone_number
        profile.save(update_fields=update_fields)
        return user, profile

    def _handle_registration(self, phone_number, segments):
        if not segments:
            return self._text(UssdSubscriber.Language.ENGLISH, "select_language")

        language = LANGUAGE_MAP.get(segments[0])
        if language is None:
            return self._text(UssdSubscriber.Language.ENGLISH, "invalid_language")

        registration_segments = segments[1:]
        if not registration_segments:
            return self._text(language, "welcome_name")

        full_name = registration_segments[0]
        if len(registration_segments) == 1:
            return self._text(language, "select_role")

        role = ROLE_MAP.get(registration_segments[1])
        if role is None:
            return self._text(language, "invalid_role")

        user, _profile = self._sync_backend_profile(phone_number or "unknown", full_name, role)
        UssdSubscriber.objects.update_or_create(
            phone_number=phone_number or "unknown",
            defaults={
                "user": user,
                "full_name": full_name,
                "role": role,
                "preferred_language": language,
            },
        )
        return self._main_menu(language)

    def _handle_market_prices(self, segments, language):
        service = get_market_price_service()
        if len(segments) == 1:
            try:
                market_lines = [f"{option}. {item['name']}" for option, item in service.get_market_options()]
            except LiveMarketPricesUnavailable:
                return (
                    "END Market prices not available right now."
                    if language == UssdSubscriber.Language.ENGLISH
                    else "END Bei za soko hazipatikani kwa sasa."
                )
            title = "CON Select market\n" if language == UssdSubscriber.Language.ENGLISH else "CON Chagua soko\n"
            back = "\n0. Back" if language == UssdSubscriber.Language.ENGLISH else "\n0. Rudi"
            return title + "\n".join(market_lines) + back
        if len(segments) == 2:
            try:
                market_lookup = dict(service.get_market_options())
                selected_market = market_lookup.get(segments[1])
                if selected_market is None:
                    return "END Invalid market selection." if language == UssdSubscriber.Language.ENGLISH else "END Chaguo la soko si sahihi."
                commodity_lines = [
                    f"{option}. {self._translate_commodity(item['name'], language)}"
                    for option, item in service.get_commodity_options(selected_market["market_id"])
                ]
            except LiveMarketPricesUnavailable:
                return "END Market prices not available right now." if language == UssdSubscriber.Language.ENGLISH else "END Bei za soko hazipatikani kwa sasa."
            if not commodity_lines:
                return "END No commodities available for this market right now." if language == UssdSubscriber.Language.ENGLISH else "END Hakuna mazao ya soko hili kwa sasa."
            title = "CON Select commodity\n" if language == UssdSubscriber.Language.ENGLISH else "CON Chagua zao\n"
            back = "\n0. Back" if language == UssdSubscriber.Language.ENGLISH else "\n0. Rudi"
            return title + "\n".join(commodity_lines) + back
        if len(segments) == 3:
            try:
                market_lookup = dict(service.get_market_options())
                selected_market = market_lookup.get(segments[1])
                if selected_market is None:
                    return "END Invalid market selection." if language == UssdSubscriber.Language.ENGLISH else "END Chaguo la soko si sahihi."
                commodity_lookup = dict(service.get_commodity_options(selected_market["market_id"]))
                selected_commodity = commodity_lookup.get(segments[2])
                if selected_commodity is None:
                    return "END Invalid commodity selection." if language == UssdSubscriber.Language.ENGLISH else "END Chaguo la zao si sahihi."
                price_type_lines = [
                    f"{option}. {self._translate_price_type(item['label'], language)}"
                    for option, item in service.get_price_type_options(
                        selected_market["market_id"],
                        selected_commodity["commodity_id"],
                    )
                ]
            except LiveMarketPricesUnavailable:
                return "END Market prices not available right now." if language == UssdSubscriber.Language.ENGLISH else "END Bei za soko hazipatikani kwa sasa."
            if not price_type_lines:
                return "END No price types available for this commodity right now." if language == UssdSubscriber.Language.ENGLISH else "END Hakuna aina za bei kwa zao hili kwa sasa."
            title = "CON Select price type\n" if language == UssdSubscriber.Language.ENGLISH else "CON Chagua aina ya bei\n"
            back = "\n0. Back" if language == UssdSubscriber.Language.ENGLISH else "\n0. Rudi"
            return title + "\n".join(price_type_lines) + back
        if len(segments) == 4:
            try:
                market_lookup = dict(service.get_market_options())
                selected_market = market_lookup.get(segments[1])
                if selected_market is None:
                    return "END Invalid market selection." if language == UssdSubscriber.Language.ENGLISH else "END Chaguo la soko si sahihi."
                commodity_lookup = dict(service.get_commodity_options(selected_market["market_id"]))
                selected_commodity = commodity_lookup.get(segments[2])
                if selected_commodity is None:
                    return "END Invalid commodity selection." if language == UssdSubscriber.Language.ENGLISH else "END Chaguo la zao si sahihi."
                price_type_lookup = dict(
                    service.get_price_type_options(
                        selected_market["market_id"],
                        selected_commodity["commodity_id"],
                    )
                )
                selected_price_type = price_type_lookup.get(segments[3])
                if selected_price_type is None:
                    return "END Invalid price type." if language == UssdSubscriber.Language.ENGLISH else "END Chaguo la aina ya bei si sahihi."
                price_data = service.get_market_price(
                    selected_market["market_id"],
                    selected_commodity["commodity_id"],
                    selected_price_type["value"],
                )
            except LiveMarketPricesUnavailable:
                return "END Market prices not available right now." if language == UssdSubscriber.Language.ENGLISH else "END Bei za soko hazipatikani kwa sasa."
            min_price = (
                f"{price_data['currency']} {Decimal(price_data['min_price']):,.2f}"
                if price_data.get("min_price") is not None
                else ("Not available" if language == UssdSubscriber.Language.ENGLISH else "Haipatikani")
            )
            max_price = (
                f"{price_data['currency']} {Decimal(price_data['max_price']):,.2f}"
                if price_data.get("max_price") is not None
                else ("Not available" if language == UssdSubscriber.Language.ENGLISH else "Haipatikani")
            )
            current_price = (
                f"{price_data['currency']} {Decimal(price_data['price']):,.2f}"
                if price_data.get("price") is not None
                else ("Not available" if language == UssdSubscriber.Language.ENGLISH else "Haipatikani")
            )
            if language == UssdSubscriber.Language.SWAHILI:
                return (
                    "END Bei ya Sokoni\n"
                    f"Soko: {price_data['market']}\n"
                    f"Zao: {self._translate_commodity(price_data['commodity'], language)}\n"
                    f"Aina: {self._translate_price_type(price_data['pricetype'], language)}\n"
                    f"Tarehe: {price_data['price_date']}\n"
                    f"Bei ya Sasa: {current_price}\n"
                    f"Bei ya Chini: {min_price}\n"
                    f"Bei ya Juu: {max_price}"
                )
            return (
                "END Market Price\n"
                f"Market: {price_data['market']}\n"
                f"Commodity: {price_data['commodity']}\n"
                f"Type: {price_data['pricetype']}\n"
                f"Date: {price_data['price_date']}\n"
                f"Current Price: {current_price}\n"
                f"Min Price: {min_price}\n"
                f"Max Price: {max_price}"
            )
        return self._text(language, "invalid_choice")

    def _handle_prediction(self, segments, language):
        if len(segments) == 1:
            market_lines = [f"{option}. {name}" for option, name in self._forecast_market_options()]
            title = "CON Select market\n" if language == UssdSubscriber.Language.ENGLISH else "CON Chagua soko\n"
            back = "\n0. Back" if language == UssdSubscriber.Language.ENGLISH else "\n0. Rudi"
            return title + "\n".join(market_lines) + back
        if len(segments) == 2:
            market_lookup = dict(self._forecast_market_options())
            if segments[1] not in market_lookup:
                return "END Invalid market selection." if language == UssdSubscriber.Language.ENGLISH else "END Chaguo la soko si sahihi."
            commodity_lines = [f"{option}. {self._translate_commodity(name, language)}" for option, name in self._forecast_commodity_options()]
            title = "CON Select commodity\n" if language == UssdSubscriber.Language.ENGLISH else "CON Chagua zao\n"
            back = "\n0. Back" if language == UssdSubscriber.Language.ENGLISH else "\n0. Rudi"
            return title + "\n".join(commodity_lines) + back
        if len(segments) == 3:
            if segments[2] not in dict(self._forecast_commodity_options()):
                return "END Invalid commodity selection." if language == UssdSubscriber.Language.ENGLISH else "END Chaguo la zao si sahihi."
            if language == UssdSubscriber.Language.SWAHILI:
                return "CON Chagua aina ya bei\n1. Rejareja\n2. Jumla\n0. Rudi"
            return "CON Select price type\n1. Retail\n2. Wholesale\n0. Back"
        if len(segments) == 4:
            if segments[3] not in PRICE_TYPE_MAP:
                return "END Invalid price type." if language == UssdSubscriber.Language.ENGLISH else "END Chaguo la aina ya bei si sahihi."
            if language == UssdSubscriber.Language.SWAHILI:
                return (
                    "CON Chagua kipindi\n"
                    "1. Kila siku\n"
                    "2. Kila wiki\n"
                    "3. Kila mwezi\n"
                    "4. Msimu\n"
                    "0. Rudi"
                )
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
                return "END Invalid market selection." if language == UssdSubscriber.Language.ENGLISH else "END Chaguo la soko si sahihi."
            if commodity is None:
                return "END Invalid commodity selection." if language == UssdSubscriber.Language.ENGLISH else "END Chaguo la zao si sahihi."
            if price_type is None:
                return "END Invalid price type." if language == UssdSubscriber.Language.ENGLISH else "END Chaguo la aina ya bei si sahihi."
            if period is None:
                return "END Invalid period selection." if language == UssdSubscriber.Language.ENGLISH else "END Chaguo la kipindi si sahihi."

            try:
                result = get_cached_prediction(
                    market=market,
                    commodity=commodity,
                    pricetype=price_type[0],
                    period=period,
                )
            except ForecastUnavailable:
                return "END Prediction not available right now." if language == UssdSubscriber.Language.ENGLISH else "END Utabiri haupatikani kwa sasa."

            period_label = {
                "daily": f"Day: {result.target_date.isoformat()}",
                "weekly": f"Week: {result.target_date.isoformat()} to {result.period_end.isoformat()}",
                "monthly": f"Month: {result.target_date.isoformat()} to {result.period_end.isoformat()}",
                "seasonal": (
                    f"Season: {result.season} "
                    f"({result.target_date.isoformat()} to {result.period_end.isoformat()})"
                ),
            }[result.period]
            if language == UssdSubscriber.Language.SWAHILI:
                period_label = {
                    "daily": f"Siku: {result.target_date.isoformat()}",
                    "weekly": f"Wiki: {result.target_date.isoformat()} hadi {result.period_end.isoformat()}",
                    "monthly": f"Mwezi: {result.target_date.isoformat()} hadi {result.period_end.isoformat()}",
                    "seasonal": (
                        f"Msimu: {result.season} "
                        f"({result.target_date.isoformat()} hadi {result.period_end.isoformat()})"
                    ),
                }[result.period]
                return (
                    "END Bei Iliyotabiriwa\n"
                    f"Soko: {result.market.name}\n"
                    f"Zao: {self._translate_commodity(result.commodity, language)}\n"
                    f"Aina: {self._translate_price_type(result.pricetype, language)} ({result.unit})\n"
                    f"{period_label}\n"
                    f"Bei: {result.currency} {result.predicted_price:,.2f}"
                )
            return (
                "END Predicted Price\n"
                f"Market: {result.market.name}\n"
                f"Commodity: {result.commodity}\n"
                f"Type: {result.pricetype} ({result.unit})\n"
                f"{period_label}\n"
                f"Price: {result.currency} {result.predicted_price:,.2f}"
            )
        return self._text(language, "invalid_choice")

    def _handle_recommendations(self, subscriber, segments, language):
        if len(segments) == 1:
            commodity_lines = [f"{option}. {self._translate_commodity(name, language)}" for option, name in self._forecast_commodity_options()]
            title = "CON Select commodity\n" if language == UssdSubscriber.Language.ENGLISH else "CON Chagua zao\n"
            back = "\n0. Back" if language == UssdSubscriber.Language.ENGLISH else "\n0. Rudi"
            return title + "\n".join(commodity_lines) + back
        if len(segments) == 2:
            if segments[1] not in dict(self._forecast_commodity_options()):
                return "END Invalid commodity selection." if language == UssdSubscriber.Language.ENGLISH else "END Chaguo la zao si sahihi."
            return self._recommendation_prompt_lines(subscriber, language)
        if len(segments) == 3:
            commodity = dict(self._forecast_commodity_options()).get(segments[1])
            recommendation_type = {
                "1": "time",
                "2": "market",
            }.get(segments[2])
            if commodity is None:
                return "END Invalid commodity selection." if language == UssdSubscriber.Language.ENGLISH else "END Chaguo la zao si sahihi."
            if recommendation_type is None:
                return "END Invalid recommendation option." if language == UssdSubscriber.Language.ENGLISH else "END Chaguo la pendekezo si sahihi."

            try:
                recommendation = get_cached_recommendation(
                    role=subscriber.role,
                    commodity=commodity,
                    recommendation_type=recommendation_type,
                )
            except LookupError:
                return "END Recommendation not available right now." if language == UssdSubscriber.Language.ENGLISH else "END Pendekezo halipatikani kwa sasa."

            if recommendation.recommendation_type == "time":
                if language == UssdSubscriber.Language.SWAHILI:
                    action = "kununua" if subscriber.role == UssdSubscriber.Role.BUYER else "kuuza"
                    window = (
                        "sasa"
                        if recommendation.window_start and recommendation.window_start <= recommendation.target_date <= recommendation.window_end
                        else f"{recommendation.window_start.isoformat()} hadi {recommendation.window_end.isoformat()}"
                    )
                    return (
                        "END Pendekezo\n"
                        f"Muda bora wa {action}: {window}\n"
                        f"Msimu: {recommendation.season}\n"
                        f"Mwelekeo: {self._translate_trend(recommendation.trend, language)}\n"
                        f"Sababu: Mfumo unatabiri kipindi kizuri cha {action} katika msimu wa {recommendation.season}."
                    )
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
            if language == UssdSubscriber.Language.SWAHILI:
                action = "kununua" if subscriber.role == UssdSubscriber.Role.BUYER else "kuuza"
                return (
                    "END Pendekezo\n"
                    f"Soko bora la {action}: {recommendation.market.name if recommendation.market else '-'}\n"
                    f"Mwelekeo: {self._translate_trend(recommendation.trend, language)}\n"
                    f"Sababu: Soko hili lina bei inayotabiriwa kuwa bora zaidi leo."
                )
            return (
                "END Recommendation\n"
                f"{recommendation.summary}\n"
                f"Trend: {recommendation.trend}\n"
                f"Reason: {recommendation.reason}"
            )
        return self._text(language, "invalid_choice")

    def _handle_weather_forecast(self, segments, language):
        region_options = get_weather_region_options()
        if len(segments) == 1:
            region_lines = [f"{option}. {region.name}" for option, region in region_options]
            title = "CON Select region\n" if language == UssdSubscriber.Language.ENGLISH else "CON Chagua eneo\n"
            back = "\n0. Back" if language == UssdSubscriber.Language.ENGLISH else "\n0. Rudi"
            return title + "\n".join(region_lines) + back

        if len(segments) == 2:
            region = dict(region_options).get(segments[1])
            if region is None:
                return "END Invalid region selection." if language == UssdSubscriber.Language.ENGLISH else "END Chaguo la eneo si sahihi."
            try:
                forecast = get_weather_service().fetch_weekly_forecast(region)
            except WeatherForecastUnavailable:
                return "END Weather forecast not available right now." if language == UssdSubscriber.Language.ENGLISH else "END Utabiri wa hali ya hewa haupatikani kwa sasa."

            day_lines = [
                (
                    f"{self._translate_day(day['weekday'], language)}: {self._translate_weather_condition(day['condition'], language)}, "
                    f"{self._translate_weather_guidance(day['guidance'], language)}, {day['temperature']}"
                )
                for day in forecast["days"]
            ]
            if language == UssdSubscriber.Language.SWAHILI:
                return (
                    "END Utabiri wa Hali ya Hewa\n"
                    f"Eneo: {forecast['region']}\n"
                    f"Msimu: {forecast['season']}\n"
                    + "\n".join(day_lines)
                )
            return (
                "END Weather Forecast\n"
                f"Region: {forecast['region']}\n"
                f"Season: {forecast['season']}\n"
                + "\n".join(day_lines)
            )
        return self._text(language, "invalid_choice")

    def _profile_for_subscriber(self, subscriber):
        profile_role = self._resolve_profile_role(subscriber.role)
        if subscriber.user_id:
            profile, _created = Profile.objects.get_or_create(
                user=subscriber.user,
                defaults={
                    "role": profile_role,
                    "phone_number": subscriber.phone_number,
                },
            )
            profile_needs_update = False
            if profile.role_id != profile_role.id:
                profile.role = profile_role
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

    def _account_menu(self, subscriber, language):
        if subscriber.role == UssdSubscriber.Role.FARMER:
            if language == UssdSubscriber.Language.SWAHILI:
                return (
                    "CON Akaunti Yangu\n"
                    "1. Tazama Wasifu\n"
                    "2. Badili Jukumu\n"
                    "3. Weka Tahadhari ya Bei\n"
                    "4. Sasisha Eneo la Shamba\n"
                    "5. Sasisha Kikundi cha Shamba\n"
                    "0. Rudi"
                )
            return (
                "CON My Account\n"
                "1. View Profile\n"
                "2. Change Role\n"
                "3. Set Price Alert\n"
                "4. Update Farm Location\n"
                "5. Update Farm Group\n"
                "0. Back"
            )
        if language == UssdSubscriber.Language.SWAHILI:
            return (
                "CON Akaunti Yangu\n"
                "1. Tazama Wasifu\n"
                "2. Badili Jukumu\n"
                "3. Weka Tahadhari ya Bei\n"
                "0. Rudi"
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
        if subscriber.preferred_language == UssdSubscriber.Language.SWAHILI:
            message = (
                f"END Jina: {subscriber.full_name}, Jukumu: {self._translate_role(subscriber.role, subscriber.preferred_language)}, "
                f"Simu: {subscriber.phone_number}"
            )
            if subscriber.role == UssdSubscriber.Role.FARMER:
                farm_location = profile.farm_location or "Haijawekwa"
                farm_group = profile.farm_group or "Haijawekwa"
                message += f", Eneo la Shamba: {farm_location}, Kikundi cha Shamba: {farm_group}"
            maize_alert_text = f"TZS {maize_alert:.2f}" if maize_alert is not None else "Haijawekwa"
            rice_alert_text = f"TZS {rice_alert:.2f}" if rice_alert is not None else "Haijawekwa"
            message += f", Tahadhari ya Mahindi: {maize_alert_text}, Tahadhari ya Mchele: {rice_alert_text}"
            return message
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

    def _handle_account(self, subscriber, segments, language):
        profile = self._profile_for_subscriber(subscriber)

        if len(segments) == 1:
            return self._account_menu(subscriber, language)

        if len(segments) == 2:
            if segments[1] == "1":
                return self._view_profile_response(subscriber, profile)
            if segments[1] == "2":
                if language == UssdSubscriber.Language.SWAHILI:
                    return "CON Badili jukumu\n1. Mkulima\n2. Mjasiriamali\n3. Mnunuzi\n0. Rudi"
                return "CON Change role\n1. Farmer\n2. Entrepreneur\n3. Buyer\n0. Back"
            if segments[1] == "3":
                if language == UssdSubscriber.Language.SWAHILI:
                    return "CON Chagua zao la tahadhari\n1. Mahindi\n2. Mchele\n0. Rudi"
                return "CON Select commodity alert\n1. Maize\n2. Rice\n0. Back"
            if segments[1] == "4" and subscriber.role == UssdSubscriber.Role.FARMER:
                return "CON Enter farm location" if language == UssdSubscriber.Language.ENGLISH else "CON Weka eneo la shamba"
            if segments[1] == "5" and subscriber.role == UssdSubscriber.Role.FARMER:
                return "CON Enter farm group" if language == UssdSubscriber.Language.ENGLISH else "CON Weka kikundi cha shamba"
            return self._text(language, "invalid_account_option")

        if len(segments) == 3:
            if segments[1] == "2":
                role = ROLE_MAP.get(segments[2])
                if role is None:
                    return self._text(language, "invalid_role")
                profile_role = self._resolve_profile_role(role)
                subscriber.role = role
                subscriber.save(update_fields=["role", "updated_at"])
                profile.role = profile_role
                profile.save(update_fields=["role", "updated_at"])
                if language == UssdSubscriber.Language.SWAHILI:
                    return f"END Jukumu limebadilishwa kuwa {self._translate_role(subscriber.role, language)}."
                return f"END Role updated to {subscriber.get_role_display()}."
            if segments[1] == "3":
                if segments[2] not in COMMODITY_MAP:
                    return "END Invalid commodity selection." if language == UssdSubscriber.Language.ENGLISH else "END Chaguo la zao si sahihi."
                commodity_name = self._translate_commodity(COMMODITY_MAP[segments[2]][1], language)
                if language == UssdSubscriber.Language.SWAHILI:
                    return f"CON Weka bei lengwa ya {commodity_name}"
                return f"CON Enter target price for {commodity_name}"
            if segments[1] == "4" and subscriber.role == UssdSubscriber.Role.FARMER:
                profile.farm_location = segments[2]
                profile.save(update_fields=["farm_location", "updated_at"])
                if language == UssdSubscriber.Language.SWAHILI:
                    return f"END Eneo la shamba limesasishwa kuwa {profile.farm_location}."
                return f"END Farm location updated to {profile.farm_location}."
            if segments[1] == "5" and subscriber.role == UssdSubscriber.Role.FARMER:
                profile.farm_group = segments[2]
                profile.save(update_fields=["farm_group", "updated_at"])
                if language == UssdSubscriber.Language.SWAHILI:
                    return f"END Kikundi cha shamba kimesasishwa kuwa {profile.farm_group}."
                return f"END Farm group updated to {profile.farm_group}."
            return self._text(language, "invalid_account_option")

        if len(segments) == 4 and segments[1] == "3":
            commodity = COMMODITY_MAP.get(segments[2])
            if commodity is None:
                return "END Invalid commodity selection." if language == UssdSubscriber.Language.ENGLISH else "END Chaguo la zao si sahihi."
            try:
                target_price = Decimal(segments[3])
            except InvalidOperation:
                return "END Invalid price. Enter a numeric target price." if language == UssdSubscriber.Language.ENGLISH else "END Bei si sahihi. Weka namba ya bei lengwa."
            UssdPriceAlert.objects.update_or_create(
                subscriber=subscriber,
                commodity=commodity[0],
                defaults={"target_price": target_price, "is_active": True},
            )
            if language == UssdSubscriber.Language.SWAHILI:
                return (
                    f"END Tahadhari ya bei imehifadhiwa kwa {self._translate_commodity(commodity[1], language)} kwa TZS {target_price:.2f}. "
                    "Utatumiwa SMS bei hiyo ikifikiwa."
                )
            return (
                f"END Price alert saved for {commodity[1]} at TZS {target_price:.2f}. "
                "You will be notified by SMS when the price is reached."
            )
        return self._text(language, "invalid_choice")

    def post(self, request, *args, **kwargs):
        session_id = self._get_value(request, "sessionId")
        service_code = self._get_value(request, "serviceCode")
        phone_number = self._get_value(request, "phoneNumber")
        text = self._get_value(request, "text")

        _ = session_id, service_code, phone_number
        raw_segments = [segment.strip() for segment in text.split("*") if segment.strip()]
        segments = self._normalize_segments(text)
        subscriber = UssdSubscriber.objects.select_related("user").filter(phone_number=phone_number).first()
        if subscriber is not None:
            segments = self._strip_completed_registration_segments(subscriber, segments)
        language = (
            subscriber.preferred_language
            if subscriber is not None
            else LANGUAGE_MAP.get(segments[0], UssdSubscriber.Language.ENGLISH)
            if segments
            else UssdSubscriber.Language.ENGLISH
        )

        if self._is_exit(raw_segments):
            response_text = self._text(language, "goodbye")
        elif subscriber is None:
            response_text = self._handle_registration(phone_number, segments)
        elif not segments:
            response_text = self._main_menu(language)
        elif segments[0] == "1":
            response_text = self._handle_market_prices(segments, language)
        elif segments[0] == "2":
            response_text = self._handle_prediction(segments, language)
        elif segments[0] == "3":
            response_text = self._handle_recommendations(subscriber, segments, language)
        elif segments[0] == "4":
            response_text = self._handle_weather_forecast(segments, language)
        elif segments[0] == "5":
            response_text = self._handle_account(subscriber, segments, language)
        else:
            response_text = self._text(language, "invalid_choice")

        return HttpResponse(response_text, content_type="text/plain")

    def get(self, request, *args, **kwargs):
        return self.post(request, *args, **kwargs)
