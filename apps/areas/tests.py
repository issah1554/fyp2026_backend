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

        response = self.client.post(
            "/api/v1/areas/bulk",
            [
                {"level": "region", "path": ["Morogoro"]},
                {"level": "district", "path": ["Morogoro", "Kilombero"]},
                {"level": "ward", "path": ["Morogoro", "Kilombero", "Ifakara"]},
            ],
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data["success"])
        self.assertEqual(response.data["message"], "Administrative area bulk import completed.")
        self.assertEqual(len(response.data["data"]["created"]), 3)
        self.assertEqual(response.data["meta"]["created_count"], 3)
        self.assertEqual(response.data["meta"]["skipped_count"], 0)
        region = AdmArea.objects.get(name="Morogoro", level="region")
        district = AdmArea.objects.get(name="Kilombero", level="district", parent=region)
        self.assertTrue(AdmArea.objects.filter(name="Ifakara", level="ward", parent=district).exists())

    def test_bulk_area_import_is_idempotent_by_path(self):
        self.client.force_authenticate(self.admin)
        payload = [
            {"level": "ward", "path": ["Morogoro", "Kilombero", "Ifakara"]},
            {"level": "ward", "path": ["Morogoro", "Kilombero", "Mngeta"]},
        ]

        first_response = self.client.post("/api/v1/areas/bulk", payload, format="json")
        second_response = self.client.post("/api/v1/areas/bulk", payload, format="json")

        self.assertEqual(first_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second_response.status_code, status.HTTP_200_OK)
        self.assertEqual(second_response.data["meta"]["created_count"], 0)
        self.assertEqual(second_response.data["meta"]["skipped_count"], 2)
        self.assertEqual(second_response.data["data"]["skipped"][0]["reason"], "duplicate")
        self.assertEqual(AdmArea.objects.filter(name="Morogoro", level="region").count(), 1)
        self.assertEqual(AdmArea.objects.filter(name="Kilombero", level="district").count(), 1)
        self.assertEqual(AdmArea.objects.filter(level="ward").count(), 2)

    def test_bulk_area_import_creates_new_rows_and_reports_duplicates(self):
        self.client.force_authenticate(self.admin)
        region = AdmArea.objects.create(name="Morogoro", level="region")
        district = AdmArea.objects.create(name="Kilombero", level="district", parent=region)
        AdmArea.objects.create(name="Ifakara", level="ward", parent=district)

        response = self.client.post(
            "/api/v1/areas/bulk",
            [
                {"level": "ward", "path": ["Morogoro", "Kilombero", "Ifakara"]},
                {"level": "ward", "path": ["Morogoro", "Kilombero", "Mngeta"]},
            ],
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["meta"]["created_count"], 1)
        self.assertEqual(response.data["meta"]["skipped_count"], 1)
        self.assertEqual(response.data["data"]["skipped"][0]["path"], ["Morogoro", "Kilombero", "Ifakara"])
        self.assertTrue(AdmArea.objects.filter(name="Mngeta", level="ward", parent=district).exists())

    def test_bulk_area_import_rejects_invalid_path_for_level(self):
        self.client.force_authenticate(self.admin)

        response = self.client.post(
            "/api/v1/areas/bulk",
            [{"level": "ward", "path": ["Ifakara"]}],
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.data["success"])
        self.assertTrue(response.data["errors"])

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
