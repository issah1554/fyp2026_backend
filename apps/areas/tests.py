from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.auth.models import Profile

from .models import AdmArea


class AreasApiTests(APITestCase):
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

        self.farmer = get_user_model().objects.create_user(
            username="farmer",
            email="farmer@example.com",
            password="StrongPass123",
        )
        Profile.objects.create(
            user=self.farmer,
            role=Profile.Role.FARMER,
            email_verified_at=timezone.now(),
        )

    def test_admin_can_create_and_list_adm_areas(self):
        self.client.force_authenticate(self.admin)

        create_response = self.client.post(
            "/api/v1/areas/",
            {
                "name": "Dar es Salaam",
                "level": "region",
            },
            format="json",
        )
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(create_response.data["success"])
        parent_id = create_response.data["data"]["area_id"]

        child_response = self.client.post(
            "/api/v1/areas/",
            {
                "name": "Kinondoni",
                "level": "district",
                "parent_id": parent_id,
            },
            format="json",
        )
        self.assertEqual(child_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(child_response.data["data"]["parent"]["name"], "Dar es Salaam")

        list_response = self.client.get("/api/v1/areas/")
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(list_response.data["data"]), 2)

    def test_farmer_cannot_create_adm_areas(self):
        self.client.force_authenticate(self.farmer)
        create_response = self.client.post(
            "/api/v1/areas/",
            {
                "name": "Tanga",
                "level": "region",
            },
            format="json",
        )
        self.assertEqual(create_response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_bulk_create_adm_areas_without_trailing_slash(self):
        self.client.force_authenticate(self.admin)
        region = AdmArea.objects.create(name="Morogoro", level="region")

        response = self.client.post(
            "/api/v1/areas/bulk",
            [
                {"name": "Ifakara", "level": "district", "parent_id": region.public_id},
                {"name": "Kilombero", "level": "district", "parent_id": region.public_id},
            ],
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data["success"])
        self.assertEqual(response.data["message"], "Administrative areas created successfully.")
        self.assertEqual(len(response.data["data"]), 2)
        self.assertTrue(AdmArea.objects.filter(name="Ifakara").exists())
        self.assertTrue(AdmArea.objects.filter(name="Kilombero").exists())

    def test_district_and_ward_require_correct_parent_levels(self):
        self.client.force_authenticate(self.admin)
        region = AdmArea.objects.create(name="Morogoro", level="region")
        district = AdmArea.objects.create(name="Kilombero", level="district", parent=region)

        missing_parent_response = self.client.post(
            "/api/v1/areas/",
            {"name": "Ifakara", "level": "district"},
            format="json",
        )
        self.assertEqual(missing_parent_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("parent_id", missing_parent_response.data["errors"])

        wrong_parent_response = self.client.post(
            "/api/v1/areas/",
            {"name": "Bad Ward", "level": "ward", "parent_id": region.public_id},
            format="json",
        )
        self.assertEqual(wrong_parent_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("parent_id", wrong_parent_response.data["errors"])

        ward_response = self.client.post(
            "/api/v1/areas/",
            {"name": "Ifakara", "level": "ward", "parent_id": district.public_id},
            format="json",
        )
        self.assertEqual(ward_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(ward_response.data["data"]["parent"]["name"], "Kilombero")

    def test_region_cannot_include_parent(self):
        self.client.force_authenticate(self.admin)
        region = AdmArea.objects.create(name="Morogoro", level="region")

        response = self.client.post(
            "/api/v1/areas/",
            {"name": "Nested Region", "level": "region", "parent_id": region.public_id},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("parent_id", response.data["errors"])

    def test_unauthenticated_can_list_adm_areas(self):
        AdmArea.objects.create(name="Public Region", level="region")
        self.client.force_authenticate(user=None)
        list_response = self.client.get("/api/v1/areas/")
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertTrue(list_response.data["success"])

    def test_adm_areas_filtering(self):
        parent_region = AdmArea.objects.create(name="Arusha", level="region")
        AdmArea.objects.create(name="Meru", level="district", parent=parent_region)

        self.client.force_authenticate(user=None)

        level_response = self.client.get("/api/v1/areas/", {"level": "region"})
        self.assertEqual(level_response.status_code, status.HTTP_200_OK)
        self.assertTrue(any(x["name"] == "Arusha" for x in level_response.data["data"]))

        search_response = self.client.get("/api/v1/areas/", {"search": "eru"})
        self.assertEqual(search_response.status_code, status.HTTP_200_OK)
        self.assertTrue(any(x["name"] == "Meru" for x in search_response.data["data"]))
        self.assertFalse(any(x["name"] == "Arusha" for x in search_response.data["data"]))

        parent_response = self.client.get("/api/v1/areas/", {"parent_id": parent_region.public_id})
        self.assertEqual(parent_response.status_code, status.HTTP_200_OK)
        self.assertTrue(any(x["name"] == "Meru" for x in parent_response.data["data"]))
        self.assertFalse(any(x["name"] == "Arusha" for x in parent_response.data["data"]))
