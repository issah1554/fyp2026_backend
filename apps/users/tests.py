from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.auth.models import Profile


class UserAdminApiTests(APITestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_user(
            username="admin",
            email="admin@example.com",
            password="StrongPass123",
        )
        Profile.objects.create(
            user=self.admin,
            role=Profile.Role.ADMIN,
            email_verified_at=timezone.now(),
        )
        self.client.force_authenticate(self.admin)

    def test_admin_can_create_and_list_users(self):
        create_response = self.client.post(
            "/api/v1/users/",
            {
                "username": "buyer1",
                "email": "buyer1@example.com",
                "password": "StrongPass123",
                "first_name": "Buyer",
                "last_name": "One",
                "role": "buyer",
                "phone_number": "+255700000010",
                "organization": "Market Buyers",
            },
            format="json",
        )

        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(create_response.data["success"])
        self.assertEqual(create_response.data["data"]["username"], "buyer1")
        self.assertRegex(create_response.data["data"]["user_id"], r"^[1-9BCDFGHJKLMNPQRSTVWXYZbcdfghjkmnpqrstvwxyz]{10}$")
        self.assertNotIn("id", create_response.data["data"])
        self.assertEqual(create_response.data["data"]["profile"]["role"], "buyer")

        list_response = self.client.get("/api/v1/users/")
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertTrue(list_response.data["success"])
        self.assertGreaterEqual(len(list_response.data["data"]), 2)

    def test_admin_can_retrieve_update_and_delete_user_by_public_id(self):
        user = get_user_model().objects.create_user(
            username="farmer1",
            email="farmer1@example.com",
            password="StrongPass123",
        )
        profile = Profile.objects.create(user=user, role=Profile.Role.FARMER)

        detail_response = self.client.get(f"/api/v1/users/{profile.public_id}/")
        self.assertEqual(detail_response.status_code, status.HTTP_200_OK)
        self.assertEqual(detail_response.data["data"]["user_id"], profile.public_id)

        update_response = self.client.patch(
            f"/api/v1/users/{profile.public_id}/",
            {"role": "entrepreneur", "organization": "New Org", "is_active": False},
            format="json",
        )
        self.assertEqual(update_response.status_code, status.HTTP_200_OK)
        self.assertEqual(update_response.data["data"]["profile"]["role"], "entrepreneur")
        self.assertEqual(update_response.data["data"]["profile"]["organization"], "New Org")
        self.assertFalse(update_response.data["data"]["is_active"])

        delete_response = self.client.delete(f"/api/v1/users/{profile.public_id}/")
        self.assertEqual(delete_response.status_code, status.HTTP_200_OK)
        self.assertFalse(get_user_model().objects.filter(username="farmer1").exists())

    def test_non_admin_cannot_manage_users(self):
        user = get_user_model().objects.create_user(
            username="farmer2",
            email="farmer2@example.com",
            password="StrongPass123",
        )
        Profile.objects.create(user=user, role=Profile.Role.FARMER)
        self.client.force_authenticate(user)

        response = self.client.get("/api/v1/users/")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(response.data["success"])

    def test_admin_cannot_remove_own_admin_access(self):
        response = self.client.patch(
            f"/api/v1/users/{self.admin.profile.public_id}/",
            {"role": "farmer"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.data["success"])
