from django.test import TestCase
from django.urls import reverse

from django.contrib.auth import get_user_model

from apps.auth.models import Profile

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
