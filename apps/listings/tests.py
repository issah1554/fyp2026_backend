from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.auth.models import Profile
from apps.commodities.models import Commodity, CommodityCategory
from .models import AdmArea, CommodityListing, ListingImage


class ListingsApiTests(APITestCase):
    def setUp(self):
        # Create users
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

        # Create category and commodity
        self.category = CommodityCategory.objects.create(name="Cereals", description="Grain Crops")
        self.commodity = Commodity.objects.create(name="Maize", unit="kg", description="Dry Maize")
        self.commodity.categories.add(self.category)

    def test_admin_can_create_and_list_adm_areas(self):
        self.client.force_authenticate(self.admin)
        
        # Create parent area
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
        
        # Create child area
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

        # List areas
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

    def test_unauthenticated_can_list_adm_areas(self):
        AdmArea.objects.create(name="Public Region", level="region")
        self.client.force_authenticate(user=None)
        list_response = self.client.get("/api/v1/areas/")
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertTrue(list_response.data["success"])

    def test_adm_areas_filtering(self):
        parent_region = AdmArea.objects.create(name="Arusha", level="region")
        child_district = AdmArea.objects.create(name="Meru", level="district", parent=parent_region)
        
        self.client.force_authenticate(user=None)
        
        # Test level filter
        level_response = self.client.get("/api/v1/areas/", {"level": "region"})
        self.assertEqual(level_response.status_code, status.HTTP_200_OK)
        self.assertTrue(any(x["name"] == "Arusha" for x in level_response.data["data"]))
        
        # Test search filter
        search_response = self.client.get("/api/v1/areas/", {"search": "eru"})
        self.assertEqual(search_response.status_code, status.HTTP_200_OK)
        self.assertTrue(any(x["name"] == "Meru" for x in search_response.data["data"]))
        self.assertFalse(any(x["name"] == "Arusha" for x in search_response.data["data"]))
        
        # Test parent_id filter
        parent_response = self.client.get("/api/v1/areas/", {"parent_id": parent_region.public_id})
        self.assertEqual(parent_response.status_code, status.HTTP_200_OK)
        self.assertTrue(any(x["name"] == "Meru" for x in parent_response.data["data"]))
        self.assertFalse(any(x["name"] == "Arusha" for x in parent_response.data["data"]))

    def test_farmer_can_create_and_manage_listings(self):
        # Create area first as admin
        area = AdmArea.objects.create(name="Morogoro", level="region")

        # Authenticate farmer
        self.client.force_authenticate(self.farmer)
        
        create_response = self.client.post(
            "/api/v1/listings/",
            {
                "commodity_id": self.commodity.public_id,
                "adm_area_id": area.public_id,
                "title": "Fresh maize harvest",
                "description": "50 bags of premium maize",
                "price": "5000.00",
                "quantity": "50.00",
                "image_urls": ["http://example.com/maize1.jpg", "http://example.com/maize2.jpg"],
            },
            format="json",
        )
        
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(create_response.data["success"])
        listing_id = create_response.data["data"]["listing_id"]
        self.assertEqual(create_response.data["data"]["seller_id"], self.farmer.profile.public_id)
        self.assertEqual(len(create_response.data["data"]["images"]), 2)
        self.assertTrue(create_response.data["data"]["images"][0]["is_primary"])

        # List listings
        list_response = self.client.get("/api/v1/listings/")
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(list_response.data["data"]), 1)

        # Update listing
        update_response = self.client.patch(
            f"/api/v1/listings/{listing_id}/",
            {
                "price": "4800.00",
                "status": "active"
            },
            format="json",
        )
        self.assertEqual(update_response.status_code, status.HTTP_200_OK)
        self.assertEqual(update_response.data["data"]["price"], "4800.00")

        # Delete listing
        delete_response = self.client.delete(f"/api/v1/listings/{listing_id}/")
        self.assertEqual(delete_response.status_code, status.HTTP_200_OK)
        self.assertFalse(CommodityListing.objects.filter(public_id=listing_id).exists())
