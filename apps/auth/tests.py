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
        self.assertTrue(response.data["success"])
        self.assertEqual(response.data["message"], "User registered successfully.")
        self.assertEqual(response.data["data"]["username"], "amina")
        self.assertEqual(response.data["data"]["profile"]["role"], "farmer")
        self.assertNotIn("password", response.data["data"])
        self.assertIn("meta", response.data)
        self.assertIn("timestamp", response.data)

    def test_registration_validation_errors_use_response_schema(self):
        response = self.client.post(
            "/api/v1/auth/register/",
            {
                "username": "",
                "email": "not-an-email",
                "password": "short",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.data["success"])
        self.assertEqual(response.data["message"], "Validation failed.")
        self.assertIn("errors", response.data)
        self.assertIn("username", response.data["errors"])
        self.assertIn("email", response.data["errors"])
        self.assertIn("password", response.data["errors"])
        self.assertIn("meta", response.data)
        self.assertIn("timestamp", response.data)

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
        self.assertTrue(login_response.data["success"])
        self.assertEqual(login_response.data["message"], "Login successful.")
        self.assertIn("access", login_response.data["data"])
        self.assertIn("refresh", login_response.data["data"])
        self.assertEqual(login_response.data["data"]["user"]["id"], user.id)

        refresh_response = self.client.post(
            "/api/v1/auth/token/refresh/",
            {"refresh": login_response.data["data"]["refresh"]},
            format="json",
        )
        self.assertEqual(refresh_response.status_code, status.HTTP_200_OK)
        self.assertTrue(refresh_response.data["success"])
        self.assertEqual(refresh_response.data["message"], "Token refreshed successfully.")
        self.assertIn("access", refresh_response.data["data"])

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login_response.data['data']['access']}")
        me_response = self.client.get("/api/v1/auth/me/")
        self.assertEqual(me_response.status_code, status.HTTP_200_OK)
        self.assertTrue(me_response.data["success"])
        self.assertEqual(me_response.data["data"]["username"], "marketofficer")

    def test_me_requires_authentication(self):
        response = self.client.get("/api/v1/auth/me/")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertFalse(response.data["success"])
        self.assertIn("message", response.data)
        self.assertEqual(response.data["errors"], {})
        self.assertIn("meta", response.data)
        self.assertIn("timestamp", response.data)
