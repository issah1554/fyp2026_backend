from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.auth.models import Profile
from apps.areas.models import AdmArea
from apps.commodities.models import Commodity, CommodityCategory
from apps.users.models import Role
from .models import CommodityListing, ListingImage


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
            role=Role.objects.get(code=Profile.Role.ADMIN),
            email_verified_at=timezone.now(),
        )

        self.farmer = get_user_model().objects.create_user(
            username="farmer",
            email="farmer@example.com",
            password="StrongPass123",
        )
        Profile.objects.create(
            user=self.farmer,
            role=Role.objects.get(code=Profile.Role.FARMER),
            email_verified_at=timezone.now(),
        )

        # Create category and commodity
        self.category = CommodityCategory.objects.create(name="Cereals", description="Grain Crops")
        self.commodity = Commodity.objects.create(name="Maize", unit="kg", description="Dry Maize")
        self.commodity.categories.add(self.category)

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
