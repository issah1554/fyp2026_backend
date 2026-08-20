from io import StringIO
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.utils import timezone

from apps.auth.models import Profile
from apps.areas.models import AdmArea
from apps.markets.models import Market
from apps.users.models import Role
from apps.ussd.forecasting import calendar_week_end_date

from .models import (
    UssdMarketPrediction,
    UssdMarketRecommendation,
    UssdPriceAlert,
    UssdSubscriber,
)


class UssdMenuViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.market_user = get_user_model().objects.create_user(
            username="market-fixture-user",
            password="StrongPass123",
        )
        cls.market_area = AdmArea.objects.create(
            name="Morogoro",
            level=AdmArea.Level.REGION,
        )
        cls.ifakara_market = Market.all_objects.create(
            name="Ifakara Central Market",
            code="IFAKARA",
            admin_area=cls.market_area,
            status="active",
            created_by=cls.market_user,
        )
        cls.morogoro_market = Market.all_objects.create(
            name="Morogoro Central Market",
            code="MOROGORO",
            admin_area=cls.market_area,
            status="active",
            created_by=cls.market_user,
        )

    def _get_role(self, code):
        return Role.objects.get(code=code)

    def test_unregistered_user_is_prompted_to_select_language(self):
        response = self.client.post(
            reverse("ussd:menu"),
            data={
                "sessionId": "ATUssdSession123",
                "serviceCode": "*384*83342#",
                "phoneNumber": "+254700000001",
                "text": "",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "CON Select language")
        self.assertContains(response, "2. Kiswahili")

    def test_api_v1_ussd_menu_endpoint_matches_gateway_url(self):
        response = self.client.post(
            "/api/v1/ussd/menu",
            data={
                "sessionId": "ATUssdSession123",
                "serviceCode": "*384*83342#",
                "phoneNumber": "+254700000001",
                "text": "",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "CON Select language")

    def test_registration_flow_saves_subscriber_and_shows_main_menu(self):
        response = self.client.post(
            reverse("ussd:menu"),
            data={
                "sessionId": "ATUssdSession123",
                "serviceCode": "*384*83342#",
                "phoneNumber": "+254700000001",
                "text": "1*Jane Farmer*1",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "CON Main Menu")
        subscriber = UssdSubscriber.objects.get(phone_number="+254700000001")
        self.assertIsNotNone(subscriber.user)
        self.assertEqual(subscriber.preferred_language, UssdSubscriber.Language.ENGLISH)
        profile = Profile.objects.get(user=subscriber.user)
        self.assertEqual(profile.role.code, Profile.Role.FARMER)
        self.assertEqual(profile.phone_number, "+254700000001")

    def test_swahili_registration_sets_language_and_shows_translated_menu(self):
        response = self.client.post(
            reverse("ussd:menu"),
            data={
                "sessionId": "ATUssdSession123",
                "serviceCode": "*384*83342#",
                "phoneNumber": "+254700000099",
                "text": "2*Asha Mkulima*1",
            },
        )

        self.assertContains(response, "CON Menyu Kuu")
        self.assertContains(response, "Bei za Sokoni")
        subscriber = UssdSubscriber.objects.get(phone_number="+254700000099")
        self.assertEqual(subscriber.preferred_language, UssdSubscriber.Language.SWAHILI)

    @patch("apps.ussd.views.get_forecast_service")
    def test_newly_registered_user_can_continue_to_prediction_menu(self, mock_service_factory):
        mock_service_factory.return_value.get_market_options.return_value = [
            ("1", "Ifakara Central Market"),
            ("2", "Morogoro Central Market"),
        ]
        mock_service_factory.return_value.get_commodity_options.return_value = [
            ("1", "Beans"),
            ("2", "Rice"),
        ]

        registration_response = self.client.post(
            reverse("ussd:menu"),
            data={
                "sessionId": "ATUssdSession123",
                "serviceCode": "*384*83342#",
                "phoneNumber": "+254700000001",
                "text": "1*Jane Farmer*1",
            },
        )
        prediction_response = self.client.post(
            reverse("ussd:menu"),
            data={
                "sessionId": "ATUssdSession123",
                "serviceCode": "*384*83342#",
                "phoneNumber": "+254700000001",
                "text": "1*Jane Farmer*1*2",
            },
        )
        commodity_response = self.client.post(
            reverse("ussd:menu"),
            data={
                "sessionId": "ATUssdSession123",
                "serviceCode": "*384*83342#",
                "phoneNumber": "+254700000001",
                "text": "1*Jane Farmer*1*2*1",
            },
        )

        self.assertContains(registration_response, "CON Main Menu")
        self.assertContains(prediction_response, "CON Select market")
        self.assertContains(prediction_response, "Ifakara Central Market")
        self.assertContains(commodity_response, "CON Select commodity")
        self.assertContains(commodity_response, "Beans")

    def test_registration_flow_supports_buyer_and_entrepreneur_roles(self):
        entrepreneur_response = self.client.post(
            reverse("ussd:menu"),
            data={
                "sessionId": "ATUssdSession124",
                "serviceCode": "*384*83342#",
                "phoneNumber": "+254700000010",
                "text": "1*Asha Trader*2",
            },
        )
        buyer_response = self.client.post(
            reverse("ussd:menu"),
            data={
                "sessionId": "ATUssdSession125",
                "serviceCode": "*384*83342#",
                "phoneNumber": "+254700000011",
                "text": "1*Bakari Buyer*3",
            },
        )

        self.assertContains(entrepreneur_response, "CON Main Menu")
        self.assertContains(buyer_response, "CON Main Menu")
        entrepreneur_profile = Profile.objects.get(phone_number="+254700000010")
        buyer_profile = Profile.objects.get(phone_number="+254700000011")
        self.assertEqual(entrepreneur_profile.role.code, Profile.Role.ENTREPRENEUR)
        self.assertEqual(buyer_profile.role.code, Profile.Role.BUYER)

    def test_registered_farmer_can_update_farm_location_and_group(self):
        user = get_user_model().objects.create(username="+254700000001")
        profile = Profile.objects.create(
            user=user,
            role=self._get_role(Profile.Role.FARMER),
            phone_number="+254700000001",
        )
        subscriber = UssdSubscriber.objects.create(
            user=user,
            phone_number="+254700000001",
            full_name="Jane Farmer",
            role=UssdSubscriber.Role.FARMER,
        )

        location_response = self.client.post(
            reverse("ussd:menu"),
            data={
                "sessionId": "ATUssdSession123",
                "serviceCode": "*384*83342#",
                "phoneNumber": subscriber.phone_number,
                "text": "5*4*Kilombero",
            },
        )

        group_response = self.client.post(
            reverse("ussd:menu"),
            data={
                "sessionId": "ATUssdSession123",
                "serviceCode": "*384*83342#",
                "phoneNumber": subscriber.phone_number,
                "text": "5*5*Mlima Group",
            },
        )

        self.assertContains(location_response, "END Farm location updated to Kilombero.")
        self.assertContains(group_response, "END Farm group updated to Mlima Group.")
        profile.refresh_from_db()
        self.assertEqual(profile.farm_location, "Kilombero")
        self.assertEqual(profile.farm_group, "Mlima Group")

    def test_swahili_subscriber_sees_translated_account_menu(self):
        subscriber = UssdSubscriber.objects.create(
            phone_number="+254700000013",
            full_name="Asha Farmer",
            preferred_language=UssdSubscriber.Language.SWAHILI,
            role=UssdSubscriber.Role.FARMER,
        )

        response = self.client.post(
            reverse("ussd:menu"),
            data={
                "sessionId": "ATUssdSession126",
                "serviceCode": "*384*83342#",
                "phoneNumber": subscriber.phone_number,
                "text": "5",
            },
        )

        self.assertContains(response, "CON Akaunti Yangu")
        self.assertContains(response, "Weka Tahadhari ya Bei")
        self.assertContains(response, "Badili Lugha")

    def test_account_menu_allows_english_user_to_change_language(self):
        subscriber = UssdSubscriber.objects.create(
            phone_number="+254700000014",
            full_name="Jane Farmer",
            preferred_language=UssdSubscriber.Language.ENGLISH,
            role=UssdSubscriber.Role.FARMER,
        )

        menu_response = self.client.post(
            reverse("ussd:menu"),
            data={
                "sessionId": "ATUssdSession127",
                "serviceCode": "*384*83342#",
                "phoneNumber": subscriber.phone_number,
                "text": "5",
            },
        )
        change_response = self.client.post(
            reverse("ussd:menu"),
            data={
                "sessionId": "ATUssdSession127",
                "serviceCode": "*384*83342#",
                "phoneNumber": subscriber.phone_number,
                "text": "5*6",
            },
        )
        save_response = self.client.post(
            reverse("ussd:menu"),
            data={
                "sessionId": "ATUssdSession127",
                "serviceCode": "*384*83342#",
                "phoneNumber": subscriber.phone_number,
                "text": "5*6*2",
            },
        )

        self.assertContains(menu_response, "Change Language")
        self.assertContains(change_response, "CON Select language")
        self.assertContains(save_response, "END Lugha imebadilishwa kuwa Kiswahili.")
        subscriber.refresh_from_db()
        self.assertEqual(subscriber.preferred_language, UssdSubscriber.Language.SWAHILI)

    def test_account_menu_allows_swahili_user_to_change_language(self):
        subscriber = UssdSubscriber.objects.create(
            phone_number="+254700000015",
            full_name="Asha Farmer",
            preferred_language=UssdSubscriber.Language.SWAHILI,
            role=UssdSubscriber.Role.FARMER,
        )

        change_response = self.client.post(
            reverse("ussd:menu"),
            data={
                "sessionId": "ATUssdSession128",
                "serviceCode": "*384*83342#",
                "phoneNumber": subscriber.phone_number,
                "text": "5*6",
            },
        )
        save_response = self.client.post(
            reverse("ussd:menu"),
            data={
                "sessionId": "ATUssdSession128",
                "serviceCode": "*384*83342#",
                "phoneNumber": subscriber.phone_number,
                "text": "5*6*1",
            },
        )

        self.assertContains(change_response, "CON Chagua lugha")
        self.assertContains(save_response, "END Language updated to English.")
        subscriber.refresh_from_db()
        self.assertEqual(subscriber.preferred_language, UssdSubscriber.Language.ENGLISH)

    def test_view_profile_shows_farmer_farm_details(self):
        user = get_user_model().objects.create(username="+254700000001")
        Profile.objects.create(
            user=user,
            role=self._get_role(Profile.Role.FARMER),
            phone_number="+254700000001",
            farm_location="Morogoro Rural",
            farm_group="Tupendane Farmers",
        )
        subscriber = UssdSubscriber.objects.create(
            user=user,
            phone_number="+254700000001",
            full_name="Jane Farmer",
            role=UssdSubscriber.Role.FARMER,
        )

        response = self.client.post(
            reverse("ussd:menu"),
            data={
                "sessionId": "ATUssdSession123",
                "serviceCode": "*384*83342#",
                "phoneNumber": subscriber.phone_number,
                "text": "5*1",
            },
        )

        self.assertContains(response, "Farm Location: Morogoro Rural")
        self.assertContains(response, "Farm Group: Tupendane Farmers")
        self.assertContains(response, "Maize Alert: Not set")
        self.assertContains(response, "Rice Alert: Not set")

    @patch("apps.ussd.views.get_market_price_service")
    def test_market_prices_menu_uses_live_market_price_service(self, mock_service_factory):
        subscriber = UssdSubscriber.objects.create(
            phone_number="+254700000031",
            full_name="Market Price User",
            role=UssdSubscriber.Role.FARMER,
        )
        service = mock_service_factory.return_value
        service.get_market_options.return_value = [
            ("1", {"market_id": "market-1", "name": "Soko Matola"}),
        ]
        service.get_commodity_options.return_value = [
            ("1", {"commodity_id": "commodity-1", "name": "Rice"}),
        ]
        service.get_price_type_options.return_value = [
            ("1", {"value": "Retail", "label": "Retail"}),
        ]
        service.get_market_price.return_value = {
            "market": "Soko Matola",
            "commodity": "Rice",
            "pricetype": "Retail",
            "currency": "TZS",
            "price": "10009.00",
            "min_price": "9500.00",
            "max_price": "10500.00",
            "price_date": "2026-07-28",
        }

        market_response = self.client.post(
            reverse("ussd:menu"),
            data={
                "sessionId": "ATUssdSession131",
                "serviceCode": "*384*83342#",
                "phoneNumber": subscriber.phone_number,
                "text": "1",
            },
        )
        commodity_response = self.client.post(
            reverse("ussd:menu"),
            data={
                "sessionId": "ATUssdSession131",
                "serviceCode": "*384*83342#",
                "phoneNumber": subscriber.phone_number,
                "text": "1*1",
            },
        )
        price_type_response = self.client.post(
            reverse("ussd:menu"),
            data={
                "sessionId": "ATUssdSession131",
                "serviceCode": "*384*83342#",
                "phoneNumber": subscriber.phone_number,
                "text": "1*1*1",
            },
        )
        price_response = self.client.post(
            reverse("ussd:menu"),
            data={
                "sessionId": "ATUssdSession131",
                "serviceCode": "*384*83342#",
                "phoneNumber": subscriber.phone_number,
                "text": "1*1*1*1",
            },
        )

        self.assertContains(market_response, "CON Select market")
        self.assertContains(market_response, "Soko Matola")
        self.assertContains(commodity_response, "CON Select commodity")
        self.assertContains(commodity_response, "Rice")
        self.assertContains(price_type_response, "CON Select price type")
        self.assertContains(price_type_response, "Retail")
        self.assertContains(price_response, "END Market Price")
        self.assertContains(price_response, "Market: Soko Matola")
        self.assertContains(price_response, "Commodity: Rice")
        self.assertContains(price_response, "Type: Retail")
        self.assertContains(price_response, "Min Price: TZS 9,500.00")
        self.assertContains(price_response, "Max Price: TZS 10,500.00")

    @patch("apps.ussd.views.get_forecast_service")
    def test_registered_user_can_get_market_prediction_for_selected_options(self, mock_service_factory):
        subscriber = UssdSubscriber.objects.create(
            phone_number="+254700000001",
            full_name="Jane Farmer",
            role=UssdSubscriber.Role.FARMER,
        )
        market = Market.objects.get(name="Ifakara Central Market")
        UssdMarketPrediction.objects.create(
            market=market,
            commodity="Rice",
            pricetype="Wholesale",
            unit="100 KG",
            period="monthly",
            target_date=timezone.localdate(),
            period_end=timezone.localdate().replace(day=31),
            season="kiangazi kikuu",
            predicted_price="245000.50",
            currency="TZS",
        )
        mock_service_factory.return_value.get_market_options.return_value = [
            ("1", "Ifakara Central Market"),
            ("2", "Morogoro Central Market"),
        ]
        mock_service_factory.return_value.get_commodity_options.return_value = [
            ("1", "Beans"),
            ("2", "Rice"),
        ]

        response = self.client.post(
            reverse("ussd:menu"),
            data={
                "sessionId": "ATUssdSession123",
                "serviceCode": "*384*83342#",
                "phoneNumber": subscriber.phone_number,
                "text": "2*1*2*2*3",
            },
        )

        self.assertContains(response, "END Predicted Price")
        self.assertContains(response, "Market: Ifakara Central Market")
        self.assertContains(response, "Commodity: Rice")
        self.assertContains(response, "Type: Wholesale (100 KG)")
        self.assertContains(
            response,
            f"Month: {timezone.localdate().isoformat()} to {timezone.localdate().replace(day=31).isoformat()}",
        )
        self.assertContains(response, "Price: TZS 245,000.50")

    @patch("apps.ussd.views.send_ussd_result_sms")
    @patch("apps.ussd.views.get_forecast_service")
    def test_prediction_result_is_sent_by_sms_to_subscriber_number(
        self,
        mock_service_factory,
        mock_send_sms,
    ):
        subscriber = UssdSubscriber.objects.create(
            phone_number="+254700000041",
            full_name="Prediction SMS User",
            role=UssdSubscriber.Role.FARMER,
        )
        market = Market.objects.get(name="Ifakara Central Market")
        UssdMarketPrediction.objects.create(
            market=market,
            commodity="Rice",
            pricetype="Wholesale",
            unit="100 KG",
            period="monthly",
            target_date=timezone.localdate(),
            period_end=timezone.localdate().replace(day=31),
            season="kiangazi kikuu",
            predicted_price="245000.50",
            currency="TZS",
        )
        mock_service_factory.return_value.get_market_options.return_value = [
            ("1", "Ifakara Central Market"),
        ]
        mock_service_factory.return_value.get_commodity_options.return_value = [
            ("2", "Rice"),
        ]

        response = self.client.post(
            reverse("ussd:menu"),
            data={
                "sessionId": "ATUssdSession141",
                "serviceCode": "*384*83342#",
                "phoneNumber": subscriber.phone_number,
                "text": "2*1*2*2*3",
            },
        )

        self.assertContains(response, "END Predicted Price")
        mock_send_sms.assert_called_once()
        sent_phone_number, sent_message = mock_send_sms.call_args.args
        self.assertEqual(sent_phone_number, subscriber.phone_number)
        self.assertIn("Predicted Price", sent_message)
        self.assertNotIn("END ", sent_message)

    @patch("apps.ussd.views.get_forecast_service")
    def test_prediction_returns_not_available_when_cache_is_missing(self, mock_service_factory):
        subscriber = UssdSubscriber.objects.create(
            phone_number="+254700000001",
            full_name="Jane Farmer",
            role=UssdSubscriber.Role.FARMER,
        )
        mock_service_factory.return_value.get_market_options.return_value = [
            ("1", "Ifakara Central Market"),
            ("2", "Morogoro Central Market"),
        ]
        mock_service_factory.return_value.get_commodity_options.return_value = [
            ("1", "Beans"),
            ("2", "Rice"),
        ]

        response = self.client.post(
            reverse("ussd:menu"),
            data={
                "sessionId": "ATUssdSession123",
                "serviceCode": "*384*83342#",
                "phoneNumber": subscriber.phone_number,
                "text": "2*1*2*2*3",
            },
        )

        self.assertContains(response, "END Prediction not available right now.")

    @patch("apps.ussd.views.get_forecast_service")
    def test_prediction_menu_prompts_for_market_commodity_type_and_period(self, mock_service_factory):
        subscriber = UssdSubscriber.objects.create(
            phone_number="+254700000001",
            full_name="Jane Farmer",
            role=UssdSubscriber.Role.FARMER,
        )
        mock_service_factory.return_value.get_market_options.return_value = [
            ("1", "Ifakara Central Market"),
            ("2", "Morogoro Central Market"),
        ]
        mock_service_factory.return_value.get_commodity_options.return_value = [
            ("1", "Beans"),
            ("2", "Rice"),
        ]

        market_response = self.client.post(
            reverse("ussd:menu"),
            data={
                "sessionId": "ATUssdSession123",
                "serviceCode": "*384*83342#",
                "phoneNumber": subscriber.phone_number,
                "text": "2",
            },
        )
        commodity_response = self.client.post(
            reverse("ussd:menu"),
            data={
                "sessionId": "ATUssdSession123",
                "serviceCode": "*384*83342#",
                "phoneNumber": subscriber.phone_number,
                "text": "2*1",
            },
        )
        type_response = self.client.post(
            reverse("ussd:menu"),
            data={
                "sessionId": "ATUssdSession123",
                "serviceCode": "*384*83342#",
                "phoneNumber": subscriber.phone_number,
                "text": "2*1*2",
            },
        )
        period_response = self.client.post(
            reverse("ussd:menu"),
            data={
                "sessionId": "ATUssdSession123",
                "serviceCode": "*384*83342#",
                "phoneNumber": subscriber.phone_number,
                "text": "2*1*2*2",
            },
        )

        self.assertContains(market_response, "Ifakara Central Market")
        self.assertContains(commodity_response, "Beans")
        self.assertContains(commodity_response, "Rice")
        self.assertContains(type_response, "Select price type")
        self.assertContains(period_response, "Select period")

    @patch("apps.ussd.views.get_forecast_service")
    def test_buyer_can_get_cached_buy_recommendation(self, mock_service_factory):
        subscriber = UssdSubscriber.objects.create(
            phone_number="+254700000021",
            full_name="Buyer User",
            role=UssdSubscriber.Role.BUYER,
        )
        UssdMarketRecommendation.objects.create(
            role=UssdMarketRecommendation.Role.BUYER,
            commodity="Beans",
            recommendation_type=UssdMarketRecommendation.RecommendationType.TIME,
            action=UssdMarketRecommendation.Action.BUY,
            target_date=timezone.localdate(),
            period=UssdMarketRecommendation.Period.WEEKLY,
            season="kiangazi kikuu",
            trend=UssdMarketRecommendation.Trend.FALLING,
            recommended_price="2450.00",
            currency="TZS",
            confidence="84.00",
            summary="Wait to buy until this week.",
            reason="Best buying window is this week in kiangazi kikuu.",
        )
        mock_service_factory.return_value.get_commodity_options.return_value = [
            ("1", "Beans"),
            ("2", "Rice"),
        ]

        response = self.client.post(
            reverse("ussd:menu"),
            data={
                "sessionId": "ATUssdSession126",
                "serviceCode": "*384*83342#",
                "phoneNumber": subscriber.phone_number,
                "text": "3*1*1",
            },
        )

        self.assertContains(response, "Wait to buy until this week.")
        self.assertContains(response, "Window: week")
        self.assertContains(response, "Trend: falling")
        self.assertNotContains(response, "From:")
        self.assertNotContains(response, "To:")
        self.assertNotContains(response, "Price:")
        self.assertNotContains(response, "Confidence:")
        self.assertNotContains(response, "TZS")

    @patch("apps.ussd.views.send_ussd_result_sms")
    @patch("apps.ussd.views.get_forecast_service")
    def test_recommendation_result_is_sent_by_sms_to_subscriber_number(
        self,
        mock_service_factory,
        mock_send_sms,
    ):
        subscriber = UssdSubscriber.objects.create(
            phone_number="+254700000042",
            full_name="Recommendation SMS User",
            role=UssdSubscriber.Role.BUYER,
        )
        UssdMarketRecommendation.objects.create(
            role=UssdMarketRecommendation.Role.BUYER,
            commodity="Beans",
            recommendation_type=UssdMarketRecommendation.RecommendationType.TIME,
            action=UssdMarketRecommendation.Action.BUY,
            target_date=timezone.localdate(),
            period=UssdMarketRecommendation.Period.WEEKLY,
            season="kiangazi kikuu",
            trend=UssdMarketRecommendation.Trend.FALLING,
            recommended_price="2450.00",
            currency="TZS",
            confidence="84.00",
            summary="Wait to buy until this week.",
            reason="Best buying window is this week in kiangazi kikuu.",
        )
        mock_service_factory.return_value.get_commodity_options.return_value = [
            ("1", "Beans"),
        ]

        response = self.client.post(
            reverse("ussd:menu"),
            data={
                "sessionId": "ATUssdSession142",
                "serviceCode": "*384*83342#",
                "phoneNumber": subscriber.phone_number,
                "text": "3*1*1",
            },
        )

        self.assertContains(response, "END Recommendation")
        mock_send_sms.assert_called_once()
        sent_phone_number, sent_message = mock_send_sms.call_args.args
        self.assertEqual(sent_phone_number, subscriber.phone_number)
        self.assertIn("Recommendation", sent_message)
        self.assertNotIn("END ", sent_message)

    @patch("apps.ussd.views.get_forecast_service")
    def test_farmer_can_get_cached_sell_market_recommendation(self, mock_service_factory):
        subscriber = UssdSubscriber.objects.create(
            phone_number="+254700000022",
            full_name="Farmer User",
            role=UssdSubscriber.Role.FARMER,
        )
        market = Market.objects.get(name="Ifakara Central Market")
        UssdMarketRecommendation.objects.create(
            role=UssdMarketRecommendation.Role.FARMER,
            commodity="Rice",
            recommendation_type=UssdMarketRecommendation.RecommendationType.MARKET,
            action=UssdMarketRecommendation.Action.SELL,
            target_date=timezone.localdate(),
            market=market,
            period=UssdMarketRecommendation.Period.DAILY,
            season="kiangazi kikuu",
            trend=UssdMarketRecommendation.Trend.RISING,
            recommended_price="2810.00",
            currency="TZS",
            confidence="79.00",
            summary="Best market to sell is Ifakara Central Market.",
            reason="This market has the highest predicted daily price.",
        )
        mock_service_factory.return_value.get_commodity_options.return_value = [
            ("1", "Beans"),
            ("2", "Rice"),
        ]

        response = self.client.post(
            reverse("ussd:menu"),
            data={
                "sessionId": "ATUssdSession127",
                "serviceCode": "*384*83342#",
                "phoneNumber": subscriber.phone_number,
                "text": "3*2*2",
            },
        )

        self.assertContains(response, "Best market to sell is Ifakara Central Market.")
        self.assertContains(response, "Trend: rising")
        self.assertNotContains(response, "Market: Ifakara Central Market")
        self.assertNotContains(response, "Price:")
        self.assertNotContains(response, "Confidence:")
        self.assertNotContains(response, "TZS")

    @patch("apps.ussd.views.get_forecast_service")
    def test_recommendation_returns_not_available_when_cache_is_missing(self, mock_service_factory):
        subscriber = UssdSubscriber.objects.create(
            phone_number="+254700000023",
            full_name="Buyer User",
            role=UssdSubscriber.Role.BUYER,
        )
        mock_service_factory.return_value.get_commodity_options.return_value = [
            ("1", "Beans"),
            ("2", "Rice"),
        ]

        response = self.client.post(
            reverse("ussd:menu"),
            data={
                "sessionId": "ATUssdSession128",
                "serviceCode": "*384*83342#",
                "phoneNumber": subscriber.phone_number,
                "text": "3*1*1",
            },
        )

        self.assertContains(response, "END Recommendation not available right now.")

    def test_weather_menu_lists_supported_regions(self):
        subscriber = UssdSubscriber.objects.create(
            phone_number="+254700000024",
            full_name="Weather User",
            role=UssdSubscriber.Role.FARMER,
        )

        response = self.client.post(
            reverse("ussd:menu"),
            data={
                "sessionId": "ATUssdSession129",
                "serviceCode": "*384*83342#",
                "phoneNumber": subscriber.phone_number,
                "text": "4",
            },
        )

        self.assertContains(response, "CON Select region")
        self.assertContains(response, "Dar es Salaam")
        self.assertContains(response, "Morogoro")

    @patch("apps.ussd.views.get_weather_service")
    def test_weather_forecast_shows_season_and_weekly_forecast(self, mock_weather_service):
        subscriber = UssdSubscriber.objects.create(
            phone_number="+254700000025",
            full_name="Weather User",
            role=UssdSubscriber.Role.FARMER,
        )
        mock_weather_service.return_value.fetch_weekly_forecast.return_value = {
            "region": "Morogoro",
            "season": "kiangazi kikuu",
            "days": [
                {
                    "weekday": "Monday",
                    "condition": "Sunny",
                    "guidance": "low rain",
                    "temperature": "21-30C",
                },
                {
                    "weekday": "Tuesday",
                    "condition": "Cloudy",
                    "guidance": "possible rain",
                    "temperature": "20-28C",
                },
            ],
        }

        response = self.client.post(
            reverse("ussd:menu"),
            data={
                "sessionId": "ATUssdSession130",
                "serviceCode": "*384*83342#",
                "phoneNumber": subscriber.phone_number,
                "text": "4*2",
            },
        )

        self.assertContains(response, "END Weather Forecast")
        self.assertContains(response, "Region: Morogoro")
        self.assertContains(response, "Season: kiangazi kikuu")
        self.assertContains(response, "Monday: Sunny, low rain, 21-30C")
        self.assertContains(response, "Tuesday: Cloudy, possible rain, 20-28C")

    @patch("apps.ussd.views.send_ussd_result_sms")
    @patch("apps.ussd.views.get_weather_service")
    def test_weather_result_is_sent_by_sms_to_subscriber_number(
        self,
        mock_weather_service,
        mock_send_sms,
    ):
        subscriber = UssdSubscriber.objects.create(
            phone_number="+254700000043",
            full_name="Weather SMS User",
            role=UssdSubscriber.Role.FARMER,
        )
        mock_weather_service.return_value.fetch_weekly_forecast.return_value = {
            "region": "Morogoro",
            "season": "kiangazi kikuu",
            "days": [
                {
                    "weekday": "Monday",
                    "condition": "Sunny",
                    "guidance": "low rain",
                    "temperature": "21-30C",
                },
            ],
        }

        response = self.client.post(
            reverse("ussd:menu"),
            data={
                "sessionId": "ATUssdSession143",
                "serviceCode": "*384*83342#",
                "phoneNumber": subscriber.phone_number,
                "text": "4*2",
            },
        )

        self.assertContains(response, "END Weather Forecast")
        mock_send_sms.assert_called_once()
        sent_phone_number, sent_message = mock_send_sms.call_args.args
        self.assertEqual(sent_phone_number, subscriber.phone_number)
        self.assertIn("Weather Forecast", sent_message)
        self.assertNotIn("END ", sent_message)

    def test_view_profile_shows_saved_price_alerts(self):
        user = get_user_model().objects.create(username="+254700000001")
        Profile.objects.create(
            user=user,
            role=self._get_role(Profile.Role.FARMER),
            phone_number="+254700000001",
        )
        subscriber = UssdSubscriber.objects.create(
            user=user,
            phone_number="+254700000001",
            full_name="Jane Farmer",
            role=UssdSubscriber.Role.FARMER,
        )
        UssdPriceAlert.objects.create(
            subscriber=subscriber,
            commodity=UssdPriceAlert.Commodity.MAIZE,
            target_price="950.00",
        )
        UssdPriceAlert.objects.create(
            subscriber=subscriber,
            commodity=UssdPriceAlert.Commodity.RICE,
            target_price="2100.00",
        )

        response = self.client.post(
            reverse("ussd:menu"),
            data={
                "sessionId": "ATUssdSession123",
                "serviceCode": "*384*83342#",
                "phoneNumber": subscriber.phone_number,
                "text": "5*1",
            },
        )

        self.assertContains(response, "Maize Alert: TZS 950.00")
        self.assertContains(response, "Rice Alert: TZS 2100.00")

    def test_registered_user_can_set_price_alert(self):
        subscriber = UssdSubscriber.objects.create(
            phone_number="+254700000001",
            full_name="Jane Farmer",
            role=UssdSubscriber.Role.FARMER,
        )

        response = self.client.post(
            reverse("ussd:menu"),
            data={
                "sessionId": "ATUssdSession123",
                "serviceCode": "*384*83342#",
                "phoneNumber": subscriber.phone_number,
                "text": "5*3*1*950",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "END Price alert saved for Maize")
        self.assertTrue(
            UssdPriceAlert.objects.filter(subscriber=subscriber, commodity="maize").exists()
        )

    def test_zero_on_main_menu_exits_session(self):
        UssdSubscriber.objects.create(
            phone_number="+254700000001",
            full_name="Jane Farmer",
            role=UssdSubscriber.Role.FARMER,
        )

        response = self.client.post(
            reverse("ussd:menu"),
            data={
                "sessionId": "ATUssdSession123",
                "serviceCode": "*384*83342#",
                "phoneNumber": "+254700000001",
                "text": "0",
            },
        )

        self.assertContains(response, "END Thank you for using SmartMarket DSS. Asante! Kwa heri.")


class RefreshUssdPredictionsCommandTests(TestCase):
    @patch("apps.ussd.management.commands.refresh_ussd_predictions.PredictionRefreshService")
    def test_refresh_command_prints_results_and_summary(self, mock_service_class):
        mock_service_class.return_value.refresh_for_date.return_value = {
            "results": [object()] * 16,
            "failures": [],
        }
        mock_service_class.return_value.refresh_for_date.side_effect = (
            lambda **kwargs: kwargs["progress_callback"](
                {
                    "status": "completed",
                    "market": "Ifakara Central Market",
                    "commodity": "Beans",
                    "pricetype": "Retail",
                    "current": 1,
                    "total": 1,
                    "message": "Saved daily prediction.",
                }
            )
            or {"results": [object()] * 16, "failures": []}
        )
        stdout = StringIO()

        call_command(
            "refresh_ussd_predictions",
            "--date",
            "2026-07-18",
            stdout=stdout,
        )

        mock_service_class.return_value.refresh_for_date.assert_called_once()
        output = stdout.getvalue()
        self.assertIn("Starting cached USSD prediction refresh...", output)
        self.assertIn("Saved 16 cached USSD predictions for 2026-07-18.", output)

    @patch("apps.ussd.management.commands.refresh_ussd_predictions.PredictionRefreshService")
    def test_refresh_command_reports_skipped_failures(self, mock_service_class):
        mock_service_class.return_value.refresh_for_date.return_value = {
            "results": [object()] * 12,
            "failures": [{"market": "Ifakara Central Market"}] * 4,
        }
        stdout = StringIO()

        call_command(
            "refresh_ussd_predictions",
            "--date",
            "2026-07-18",
            stdout=stdout,
        )

        output = stdout.getvalue()
        self.assertIn("Saved 12 cached USSD predictions for 2026-07-18.", output)
        self.assertIn("Skipped 4 prediction(s) for 2026-07-18.", output)


class RefreshUssdRecommendationsCommandTests(TestCase):
    @patch("apps.ussd.management.commands.refresh_ussd_recommendations.RecommendationRefreshService")
    @patch("apps.ussd.management.commands.refresh_ussd_recommendations.get_forecast_service")
    def test_refresh_recommendations_command_prints_results_and_summary(
        self,
        _mock_forecast_service,
        mock_service_class,
    ):
        mock_service_class.return_value.refresh_for_date.return_value = {
            "results": [object()] * 12,
            "failures": [],
        }
        stdout = StringIO()

        call_command(
            "refresh_ussd_recommendations",
            "--date",
            "2026-07-18",
            stdout=stdout,
        )

        output = stdout.getvalue()
        self.assertIn("Starting cached USSD recommendation refresh...", output)
        self.assertIn("Saved 12 cached USSD recommendations for 2026-07-18.", output)


class ForecastingCalendarTests(SimpleTestCase):
    def test_weekly_period_ends_on_sunday(self):
        period_end = calendar_week_end_date(__import__("pandas").Timestamp("2026-07-18"))

        self.assertEqual(period_end.date().isoformat(), "2026-07-19")
