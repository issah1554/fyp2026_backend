from django.test import TestCase
from django.urls import reverse

from .models import UssdPriceAlert, UssdSubscriber


class UssdMenuViewTests(TestCase):
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
        self.assertTrue(UssdSubscriber.objects.filter(phone_number="+254700000001").exists())

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
