from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APITestCase


class AuthApiTests(APITestCase):
    def test_user_can_register(self):
        response = self.client.post(
            "/api/v1/auth/register/",
            {
                "username": "amina",
                "email": "amina@example.com",
                "password": "StrongPass123",
                "first_name": "Amina",
                "last_name": "Juma",
                "role": "farmer",
                "phone_number": "+255700000001",
                "organization": "Ifakara Farmers Group",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["username"], "amina")
        self.assertEqual(response.data["profile"]["role"], "farmer")
        self.assertNotIn("password", response.data)

    def test_user_can_login_refresh_and_get_profile(self):
        user = get_user_model().objects.create_user(
            username="marketofficer",
            email="officer@example.com",
            password="StrongPass123",
        )

        login_response = self.client.post(
            "/api/v1/auth/login/",
            {"username": "marketofficer", "password": "StrongPass123"},
            format="json",
        )

        self.assertEqual(login_response.status_code, status.HTTP_200_OK)
        self.assertIn("access", login_response.data)
        self.assertIn("refresh", login_response.data)
        self.assertEqual(login_response.data["user"]["id"], user.id)

        refresh_response = self.client.post(
            "/api/v1/auth/token/refresh/",
            {"refresh": login_response.data["refresh"]},
            format="json",
        )
        self.assertEqual(refresh_response.status_code, status.HTTP_200_OK)
        self.assertIn("access", refresh_response.data)

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login_response.data['access']}")
        me_response = self.client.get("/api/v1/auth/me/")
        self.assertEqual(me_response.status_code, status.HTTP_200_OK)
        self.assertEqual(me_response.data["username"], "marketofficer")

    def test_me_requires_authentication(self):
        response = self.client.get("/api/v1/auth/me/")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
