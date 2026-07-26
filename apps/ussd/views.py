from decimal import Decimal, InvalidOperation

from django.http import HttpResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from .models import UssdPriceAlert, UssdSubscriber


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

PREDICTION_DATA = {
    ("1", "1"): "END Maize next 7 days: TZS 830-880/kg, Trend: Upward, Confidence: 84%.",
    ("1", "2"): "END Rice next 7 days: TZS 2,120-2,220/kg, Trend: Stable Upward, Confidence: 81%.",
    ("2", "1"): "END Maize next month: TZS 860-940/kg, Trend: Upward, Confidence: 78%.",
    ("2", "2"): "END Rice next month: TZS 2,180-2,320/kg, Trend: Upward, Confidence: 76%.",
    ("3", "1"): "END Maize next season: TZS 900-1,020/kg, Trend: Seasonal Rise, Confidence: 72%.",
    ("3", "2"): "END Rice next season: TZS 2,240-2,420/kg, Trend: Moderate Rise, Confidence: 70%.",
}

RECOMMENDATION_DATA = {
    ("1", "1"): "END Recommendation: Wait. Reason: Maize trend is still rising, supply is tightening, seasonal demand is improving. Confidence: 86%.",
    ("1", "2"): "END Recommendation: Sell at Ifakara Central. Reason: Better maize demand, lower supply pressure, and stronger price momentum. Confidence: 82%.",
    ("2", "1"): "END Recommendation: Sell Now. Reason: Rice prices are already favorable, supply is expected to improve soon, and seasonal gains may soften. Confidence: 80%.",
    ("2", "2"): "END Recommendation: Sell at Nearby Markets. Reason: Rice has stronger buyer activity there, steady turnover, and reduced transport pressure. Confidence: 77%.",
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
            "4. My Account\n"
            "0. Exit"
        )

    def _is_exit(self, segments):
        return segments == ["0"]

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

        UssdSubscriber.objects.update_or_create(
            phone_number=phone_number or "unknown",
            defaults={"full_name": full_name, "role": role},
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
            return (
                "CON Select time period\n"
                "1. Next 7 Days\n"
                "2. Next Month\n"
                "3. Next Season\n"
                "0. Back"
            )
        if len(segments) == 2:
            if segments[1] not in {"1", "2", "3"}:
                return "END Invalid time period."
            return "CON Select commodity\n1. Maize\n2. Rice\n0. Back"
        if len(segments) == 3:
            return PREDICTION_DATA.get(
                (segments[1], segments[2]),
                "END Invalid commodity selection.",
            )
        return "END Invalid choice."

    def _handle_recommendations(self, segments):
        if len(segments) == 1:
            return "CON Select commodity\n1. Maize\n2. Rice\n0. Back"
        if len(segments) == 2:
            if segments[1] not in COMMODITY_MAP:
                return "END Invalid commodity selection."
            return "CON Select need\n1. Best Time to Sell\n2. Best Market to Sell\n0. Back"
        if len(segments) == 3:
            return RECOMMENDATION_DATA.get(
                (segments[1], segments[2]),
                "END Invalid recommendation option.",
            )
        return "END Invalid choice."

    def _handle_account(self, subscriber, segments):
        if len(segments) == 1:
            return (
                "CON My Account\n"
                "1. View Profile\n"
                "2. Change Role\n"
                "3. Set Price Alert\n"
                "0. Back"
            )
        if len(segments) == 2:
            if segments[1] == "1":
                return (
                    f"END Name: {subscriber.full_name}, Role: {subscriber.get_role_display()}, "
                    f"Phone: {subscriber.phone_number}"
                )
            if segments[1] == "2":
                return "CON Change role\n1. Farmer\n2. Entrepreneur\n3. Buyer\n0. Back"
            if segments[1] == "3":
                return "CON Select commodity alert\n1. Maize\n2. Rice\n0. Back"
            return "END Invalid account option."
        if len(segments) == 3:
            if segments[1] == "2":
                role = ROLE_MAP.get(segments[2])
                if role is None:
                    return "END Invalid role selection."
                subscriber.role = role
                subscriber.save(update_fields=["role", "updated_at"])
                return f"END Role updated to {subscriber.get_role_display()}."
            if segments[1] == "3":
                if segments[2] not in COMMODITY_MAP:
                    return "END Invalid commodity selection."
                commodity_name = COMMODITY_MAP[segments[2]][1]
                return f"CON Enter target price for {commodity_name}"
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
        subscriber = UssdSubscriber.objects.filter(phone_number=phone_number).first()

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
            response_text = self._handle_recommendations(segments)
        elif segments[0] == "4":
            response_text = self._handle_account(subscriber, segments)
        else:
            response_text = "END Invalid choice. Please try again."

        return HttpResponse(response_text, content_type="text/plain")

    def get(self, request, *args, **kwargs):
        return self.post(request, *args, **kwargs)
