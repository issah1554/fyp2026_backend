from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.auth.models import Profile
from apps.users.models import Permission, Role, RolePermission


class UserAdminApiTests(APITestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_user(
            username="admin",
            email="admin@example.com",
            password="StrongPass123",
        )
        Profile.objects.create(
            user=self.admin,
            role=Role.objects.get(code=Profile.Role.ADMIN),
            email_verified_at=timezone.now(),
        )
        self.client.force_authenticate(self.admin)

    def test_admin_can_create_and_list_users(self):
        create_response = self.client.post(
            "/api/v1/users",
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

        list_response = self.client.get("/api/v1/users")
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertTrue(list_response.data["success"])
        self.assertGreaterEqual(len(list_response.data["data"]), 2)

    def test_admin_user_create_rejects_invalid_phone_number(self):
        response = self.client.post(
            "/api/v1/users",
            {
                "username": "badphone",
                "email": "badphone@example.com",
                "password": "StrongPass123",
                "role": "buyer",
                "phone_number": "0700000010",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.data["success"])
        self.assertIn("phone_number", response.data["errors"])

    def test_admin_can_retrieve_update_and_delete_user_by_public_id(self):
        user = get_user_model().objects.create_user(
            username="farmer1",
            email="farmer1@example.com",
            password="StrongPass123",
        )
        profile = Profile.objects.create(user=user, role=Role.objects.get(code=Profile.Role.FARMER))

        detail_response = self.client.get(f"/api/v1/users/{profile.public_id}")
        self.assertEqual(detail_response.status_code, status.HTTP_200_OK)
        self.assertEqual(detail_response.data["data"]["user_id"], profile.public_id)

        update_response = self.client.patch(
            f"/api/v1/users/{profile.public_id}",
            {"role": "entrepreneur", "organization": "New Org", "is_active": False},
            format="json",
        )
        self.assertEqual(update_response.status_code, status.HTTP_200_OK)
        self.assertEqual(update_response.data["data"]["profile"]["role"], "entrepreneur")
        self.assertEqual(update_response.data["data"]["profile"]["organization"], "New Org")
        self.assertFalse(update_response.data["data"]["is_active"])

        delete_response = self.client.delete(f"/api/v1/users/{profile.public_id}")
        self.assertEqual(delete_response.status_code, status.HTTP_200_OK)
        self.assertFalse(get_user_model().objects.filter(username="farmer1").exists())

    def test_non_admin_cannot_manage_users(self):
        user = get_user_model().objects.create_user(
            username="farmer2",
            email="farmer2@example.com",
            password="StrongPass123",
        )
        Profile.objects.create(user=user, role=Role.objects.get(code=Profile.Role.FARMER))
        self.client.force_authenticate(user)

        response = self.client.get("/api/v1/users")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(response.data["success"])

    def test_admin_cannot_remove_own_admin_access(self):
        response = self.client.patch(
            f"/api/v1/users/{self.admin.profile.public_id}",
            {"role": "farmer"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.data["success"])

    def test_user_list_is_paginated_with_totals_and_filters(self):
        for index in range(12):
            user = get_user_model().objects.create_user(
                username=f"farmer{index:02d}",
                email=f"farmer{index:02d}@example.com",
                password="StrongPass123",
                is_active=index % 2 == 0,
            )
            Profile.objects.create(user=user, role=Role.objects.get(code=Profile.Role.FARMER))

        buyer = get_user_model().objects.create_user(
            username="buyer_search",
            email="buyer-search@example.com",
            password="StrongPass123",
        )
        Profile.objects.create(user=buyer, role=Role.objects.get(code=Profile.Role.BUYER), organization="Search Org")

        response = self.client.get("/api/v1/users", {"page": 2, "page_size": 5})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["data"]), 5)
        self.assertEqual(response.data["meta"]["pagination"]["page"], 2)
        self.assertEqual(response.data["meta"]["pagination"]["page_size"], 5)
        self.assertEqual(response.data["meta"]["pagination"]["total_items"], 14)
        self.assertEqual(response.data["meta"]["totals"]["total"], 14)
        self.assertEqual(response.data["meta"]["totals"]["admins"], 1)

        role_response = self.client.get("/api/v1/users", {"role": "buyer"})
        self.assertEqual(role_response.status_code, status.HTTP_200_OK)
        self.assertTrue(any(x["username"] == "buyer_search" for x in role_response.data["data"]))
        self.assertFalse(any(x["profile"]["role"] == "farmer" for x in role_response.data["data"]))

        search_response = self.client.get("/api/v1/users", {"search": "Search Org"})
        self.assertEqual(search_response.status_code, status.HTTP_200_OK)
        self.assertEqual(search_response.data["meta"]["pagination"]["total_items"], 1)
        self.assertEqual(search_response.data["data"][0]["username"], "buyer_search")

    def test_permissions_are_system_seeded_read_only_and_assignable_to_roles(self):
        permission = Permission.objects.get(code="users.list")
        list_response = self.client.get("/api/v1/users/permissions")
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertTrue(any(item["code"] == "users.list" for item in list_response.data["data"]))

        create_response = self.client.post(
            "/api/v1/users/permissions",
            {"code": "custom.permission", "name": "Custom permission"},
            format="json",
        )
        self.assertEqual(create_response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

        role_response = self.client.patch(
            "/api/v1/users/roles/admin",
            {"permission_ids": [permission.public_id]},
            format="json",
        )
        self.assertEqual(role_response.status_code, status.HTTP_200_OK)
        self.assertIn(permission.public_id, role_response.data["data"]["permission_ids"])
        admin_role = Role.objects.get(code=Profile.Role.ADMIN)
        self.assertTrue(RolePermission.objects.filter(role=admin_role, permission=permission).exists())

        update_response = self.client.patch(
            f"/api/v1/users/permissions/{permission.public_id}",
            {"name": "List managed users"},
            format="json",
        )
        self.assertEqual(update_response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

        delete_response = self.client.delete(f"/api/v1/users/permissions/{permission.public_id}")
        self.assertEqual(delete_response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        self.assertTrue(Permission.objects.filter(pk=permission.pk).exists())

    def test_role_assignment_rejects_unknown_permission(self):
        response = self.client.patch(
            "/api/v1/users/roles/admin",
            {"permission_ids": ["missing1234"]},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.data["success"])

    def test_admin_can_create_update_and_delete_custom_role(self):
        permission = Permission.objects.get(code="users.list")
        create_response = self.client.post(
            "/api/v1/users/roles",
            {
                "code": "auditor",
                "name": "Auditor",
                "description": "Read-only audit role.",
                "permission_ids": [permission.public_id],
            },
            format="json",
        )
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        role_id = create_response.data["data"]["role_id"]
        self.assertFalse(create_response.data["data"]["is_system"])
        self.assertIn(permission.public_id, create_response.data["data"]["permission_ids"])

        update_response = self.client.put(
            f"/api/v1/users/roles/{role_id}",
            {"code": "auditor", "name": "Audit Reviewer", "description": "", "permission_ids": []},
            format="json",
        )
        self.assertEqual(update_response.status_code, status.HTTP_200_OK)
        self.assertEqual(update_response.data["data"]["name"], "Audit Reviewer")
        self.assertEqual(update_response.data["data"]["permission_ids"], [])

        delete_response = self.client.delete(f"/api/v1/users/roles/{role_id}")
        self.assertEqual(delete_response.status_code, status.HTTP_200_OK)
        self.assertFalse(Role.objects.filter(public_id=role_id).exists())

    def test_system_roles_cannot_be_deleted(self):
        admin_role = Role.objects.get(code=Profile.Role.ADMIN)
        response = self.client.delete(f"/api/v1/users/roles/{admin_role.public_id}")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(Role.objects.filter(pk=admin_role.pk).exists())

    def test_seed_system_users_creates_verified_role_profiles(self):
        call_command("seed_system_users", password="StrongPass123")

        sample = get_user_model().objects.get(username="buyer_sample")
        self.assertTrue(sample.check_password("StrongPass123"))
        self.assertEqual(sample.email, "system.buyer@user.com")
        self.assertTrue(sample.is_active)
        self.assertEqual(sample.profile.role.code, Profile.Role.BUYER)
        self.assertIsNotNone(sample.profile.email_verified_at)

        call_command("seed_system_users", password="ChangedPass123")
        self.assertEqual(get_user_model().objects.filter(username="buyer_sample").count(), 1)
        sample.refresh_from_db()
        self.assertTrue(sample.check_password("ChangedPass123"))
