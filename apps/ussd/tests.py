from django.test import TestCase
from django.urls import reverse
from unittest.mock import patch

from django.contrib.auth import get_user_model

from apps.auth.models import Profile

from .models import UssdPriceAlert, UssdSubscriber


class UssdMenuViewTests(TestCase):
    @staticmethod
    def _create_fake_forecast_result():
        class FakeResult:
            market = "Ifakara Central Market"
            commodity = "Rice"
            pricetype = "Wholesale"
            unit = "100 KG"
            period = "monthly"
            target_date = "2026-07-18"
            period_end = "2026-07-31"
            season = "kiangazi kikuu"
            predicted_price = 245000.5
            currency = "TZS"

        return FakeResult()

    def test_unregistered_user_is_prompted_to_register(self):
        response = self.client.post(
            reverse("ussd:menu-no-slash"),
            data={
                "sessionId": "ATUssdSession123",
                "serviceCode": "*384*83342#",
                "phoneNumber": "+254700000001",
                "text": "",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "CON Welcome to SmartMarket DSS.")

    def test_registration_flow_saves_subscriber_and_shows_main_menu(self):
        response = self.client.post(
            reverse("ussd:menu"),
            data={
                "sessionId": "ATUssdSession123",
                "serviceCode": "*384*83342#",
                "phoneNumber": "+254700000001",
                "text": "Jane Farmer*1",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "CON Main Menu")
        subscriber = UssdSubscriber.objects.get(phone_number="+254700000001")
        self.assertIsNotNone(subscriber.user)
        profile = Profile.objects.get(user=subscriber.user)
        self.assertEqual(profile.role, Profile.Role.FARMER)
        self.assertEqual(profile.phone_number, "+254700000001")

    def test_registration_flow_supports_buyer_and_entrepreneur_roles(self):
        entrepreneur_response = self.client.post(
            reverse("ussd:menu"),
            data={
                "sessionId": "ATUssdSession124",
                "serviceCode": "*384*83342#",
                "phoneNumber": "+254700000010",
                "text": "Asha Trader*2",
            },
        )
        buyer_response = self.client.post(
            reverse("ussd:menu"),
            data={
                "sessionId": "ATUssdSession125",
                "serviceCode": "*384*83342#",
                "phoneNumber": "+254700000011",
                "text": "Bakari Buyer*3",
            },
        )

        self.assertContains(entrepreneur_response, "CON Main Menu")
        self.assertContains(buyer_response, "CON Main Menu")
        entrepreneur_profile = Profile.objects.get(phone_number="+254700000010")
        buyer_profile = Profile.objects.get(phone_number="+254700000011")
        self.assertEqual(entrepreneur_profile.role, Profile.Role.ENTREPRENEUR)
        self.assertEqual(buyer_profile.role, Profile.Role.BUYER)

    def test_registered_farmer_can_update_farm_location_and_group(self):
        user = get_user_model().objects.create(username="+254700000001")
        profile = Profile.objects.create(
            user=user,
            role=Profile.Role.FARMER,
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
                "text": "4*4*Kilombero",
            },
        )

        group_response = self.client.post(
            reverse("ussd:menu"),
            data={
                "sessionId": "ATUssdSession123",
                "serviceCode": "*384*83342#",
                "phoneNumber": subscriber.phone_number,
                "text": "4*5*Mlima Group",
            },
        )

        self.assertContains(location_response, "END Farm location updated to Kilombero.")
        self.assertContains(group_response, "END Farm group updated to Mlima Group.")
        profile.refresh_from_db()
        self.assertEqual(profile.farm_location, "Kilombero")
        self.assertEqual(profile.farm_group, "Mlima Group")

    def test_view_profile_shows_farmer_farm_details(self):
        user = get_user_model().objects.create(username="+254700000001")
        Profile.objects.create(
            user=user,
            role=Profile.Role.FARMER,
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
                "text": "4*1",
            },
        )

        self.assertContains(response, "Farm Location: Morogoro Rural")
        self.assertContains(response, "Farm Group: Tupendane Farmers")
        self.assertContains(response, "Maize Alert: Not set")
        self.assertContains(response, "Rice Alert: Not set")

    @patch("apps.ussd.views.get_forecast_service")
    def test_registered_user_can_get_market_prediction_for_selected_options(self, mock_service_factory):
        subscriber = UssdSubscriber.objects.create(
            phone_number="+254700000001",
            full_name="Jane Farmer",
            role=UssdSubscriber.Role.FARMER,
        )
        mock_service_factory.return_value.get_market_options.return_value = [
            ("1", "Ifakara Central Market"),
            ("2", "Morogoro Central Market"),
        ]
        mock_service_factory.return_value.predict.return_value = self._create_fake_forecast_result()

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
        self.assertContains(response, "Month: 2026-07-18 to 2026-07-31")
        self.assertContains(response, "Price: TZS 245,000.50")

    def test_prediction_menu_prompts_for_market_commodity_type_and_period(self):
        subscriber = UssdSubscriber.objects.create(
            phone_number="+254700000001",
            full_name="Jane Farmer",
            role=UssdSubscriber.Role.FARMER,
        )

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
        self.assertContains(commodity_response, "Select commodity")
        self.assertContains(type_response, "Select price type")
        self.assertContains(period_response, "Select period")

    def test_view_profile_shows_saved_price_alerts(self):
        user = get_user_model().objects.create(username="+254700000001")
        Profile.objects.create(
            user=user,
            role=Profile.Role.FARMER,
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
                "text": "4*1",
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
                "text": "4*3*1*950",
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
