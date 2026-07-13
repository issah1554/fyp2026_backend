from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from .models import EmailVerificationToken, PasswordResetToken, Profile


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
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
        self.assertEqual(
            response.data["message"],
            "User registered successfully. Check your email to verify your account.",
        )
        self.assertEqual(response.data["data"]["username"], "amina")
        self.assertRegex(response.data["data"]["user_id"], r"^[1-9BCDFGHJKLMNPQRSTVWXYZbcdfghjkmnpqrstvwxyz]{10}$")
        self.assertNotIn("id", response.data["data"])
        self.assertEqual(response.data["data"]["profile"]["role"], "farmer")
        self.assertFalse(response.data["data"]["profile"]["is_email_verified"])
        self.assertNotIn("password", response.data["data"])
        self.assertIn("meta", response.data)
        self.assertIn("timestamp", response.data)
        self.assertEqual(EmailVerificationToken.objects.count(), 1)
        self.assertEqual(len(mail.outbox), 1)

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

    def test_user_can_verify_email(self):
        user = get_user_model().objects.create_user(
            username="amina",
            email="amina@example.com",
            password="StrongPass123",
        )
        Profile.objects.create(user=user)
        verification_token = EmailVerificationToken.objects.create(
            user=user,
            token="valid-token",
            expires_at=timezone.now() + timedelta(hours=1),
        )

        response = self.client.post(
            "/api/v1/auth/email/verify/",
            {"token": verification_token.token},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["success"])
        self.assertEqual(response.data["message"], "Email verified successfully.")
        self.assertTrue(response.data["data"]["profile"]["is_email_verified"])
        verification_token.refresh_from_db()
        self.assertIsNotNone(verification_token.used_at)

    def test_unverified_user_cannot_login(self):
        get_user_model().objects.create_user(
            username="marketofficer",
            email="officer@example.com",
            password="StrongPass123",
        )

        response = self.client.post(
            "/api/v1/auth/login/",
            {"username": "marketofficer", "password": "StrongPass123"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertFalse(response.data["success"])
        self.assertEqual(response.data["message"], "Email address is not verified.")

    def test_invalid_login_uses_generic_invalid_credentials_message(self):
        response = self.client.post(
            "/api/v1/auth/login/",
            {"username": "missing", "password": "wrong"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertFalse(response.data["success"])
        self.assertEqual(response.data["message"], "Invalid credentials")
        self.assertEqual(response.data["errors"], {})

    def test_user_can_login_refresh_and_get_profile(self):
        user = get_user_model().objects.create_user(
            username="marketofficer",
            email="officer@example.com",
            password="StrongPass123",
        )
        Profile.objects.create(user=user, email_verified_at=timezone.now())

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
        self.assertEqual(login_response.data["data"]["user"]["user_id"], user.profile.public_id)
        self.assertNotIn("id", login_response.data["data"]["user"])

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
        self.assertEqual(me_response.data["data"]["user_id"], user.profile.public_id)

    def test_user_can_login_with_email(self):
        user = get_user_model().objects.create_user(
            username="marketofficer",
            email="officer@example.com",
            password="StrongPass123",
        )
        Profile.objects.create(user=user, email_verified_at=timezone.now())

        response = self.client.post(
            "/api/v1/auth/login/",
            {"username": "officer@example.com", "password": "StrongPass123"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["success"])
        self.assertEqual(response.data["data"]["user"]["username"], "marketofficer")

    def test_user_can_resend_email_verification(self):
        get_user_model().objects.create_user(
            username="amina",
            email="amina@example.com",
            password="StrongPass123",
        )

        response = self.client.post(
            "/api/v1/auth/email/resend/",
            {"email": "amina@example.com"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["success"])
        self.assertEqual(EmailVerificationToken.objects.count(), 1)
        self.assertEqual(len(mail.outbox), 1)

    def test_user_can_request_password_reset(self):
        get_user_model().objects.create_user(
            username="amina",
            email="amina@example.com",
            password="StrongPass123",
        )

        response = self.client.post(
            "/api/v1/auth/password/reset/request/",
            {"email": "amina@example.com"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["success"])
        self.assertEqual(response.data["message"], "If the account exists, a password reset link has been sent.")
        self.assertEqual(PasswordResetToken.objects.count(), 1)
        self.assertEqual(len(mail.outbox), 1)

    def test_password_reset_request_does_not_reveal_missing_account(self):
        response = self.client.post(
            "/api/v1/auth/password/reset/request/",
            {"email": "missing@example.com"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["success"])
        self.assertEqual(response.data["message"], "If the account exists, a password reset link has been sent.")
        self.assertEqual(PasswordResetToken.objects.count(), 0)
        self.assertEqual(len(mail.outbox), 0)

    def test_user_can_confirm_password_reset(self):
        user = get_user_model().objects.create_user(
            username="amina",
            email="amina@example.com",
            password="StrongPass123",
        )
        reset_token = PasswordResetToken.objects.create(
            user=user,
            token="valid-reset-token",
            expires_at=timezone.now() + timedelta(hours=1),
        )

        response = self.client.post(
            "/api/v1/auth/password/reset/confirm/",
            {"token": reset_token.token, "password": "NewStrongPass123"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["success"])
        self.assertEqual(response.data["message"], "Password reset successful.")
        reset_token.refresh_from_db()
        self.assertIsNotNone(reset_token.used_at)
        user.refresh_from_db()
        self.assertTrue(user.check_password("NewStrongPass123"))

    def test_me_requires_authentication(self):
        response = self.client.get("/api/v1/auth/me/")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertFalse(response.data["success"])
        self.assertIn("message", response.data)
        self.assertEqual(response.data["errors"], {})
        self.assertIn("meta", response.data)
        self.assertIn("timestamp", response.data)
