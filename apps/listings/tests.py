from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
from unittest.mock import patch

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
        self.commodity = Commodity.objects.create(name="Maize")
        self.commodity.categories.add(self.category)

    def test_farmer_can_create_and_manage_listings(self):
        # Create area first as admin
        area = AdmArea.objects.create(name="Morogoro", level="region")

        # Authenticate farmer
        self.client.force_authenticate(self.farmer)
        
        create_response = self.client.post(
            "/api/v1/listings",
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
        list_response = self.client.get("/api/v1/listings")
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(list_response.data["data"]), 1)

        # Update listing
        update_response = self.client.patch(
            f"/api/v1/listings/{listing_id}",
            {
                "price": "4800.00",
                "status": "active"
            },
            format="json",
        )
        self.assertEqual(update_response.status_code, status.HTTP_200_OK)
        self.assertEqual(update_response.data["data"]["price"], "4800.00")

        # Delete listing
        delete_response = self.client.delete(f"/api/v1/listings/{listing_id}")
        self.assertEqual(delete_response.status_code, status.HTTP_200_OK)
        self.assertFalse(CommodityListing.objects.filter(public_id=listing_id).exists())

    def test_area_filter_includes_descendant_listing_locations(self):
        region = AdmArea.objects.create(name="Morogoro", level=AdmArea.Level.REGION)
        district = AdmArea.objects.create(name="Kilombero", level=AdmArea.Level.DISTRICT, parent=region)
        ward = AdmArea.objects.create(name="Ifakara", level=AdmArea.Level.WARD, parent=district)
        other_region = AdmArea.objects.create(name="Arusha", level=AdmArea.Level.REGION)

        CommodityListing.objects.create(
            commodity=self.commodity,
            adm_area=region,
            user=self.farmer,
            title="Region listing",
            price="1000.00",
        )
        CommodityListing.objects.create(
            commodity=self.commodity,
            adm_area=district,
            user=self.farmer,
            title="District listing",
            price="2000.00",
        )
        CommodityListing.objects.create(
            commodity=self.commodity,
            adm_area=ward,
            user=self.farmer,
            title="Ward listing",
            price="3000.00",
        )
        CommodityListing.objects.create(
            commodity=self.commodity,
            adm_area=other_region,
            user=self.farmer,
            title="Other region listing",
            price="4000.00",
        )

        region_response = self.client.get("/api/v1/listings", {"area_id": region.public_id})
        self.assertEqual(region_response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            {listing["title"] for listing in region_response.data["data"]},
            {"Region listing", "District listing", "Ward listing"},
        )

        district_response = self.client.get("/api/v1/listings", {"area_id": district.public_id})
        self.assertEqual(district_response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            {listing["title"] for listing in district_response.data["data"]},
            {"District listing", "Ward listing"},
        )

        ward_response = self.client.get("/api/v1/listings", {"area_id": ward.public_id})
        self.assertEqual(ward_response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            {listing["title"] for listing in ward_response.data["data"]},
            {"Ward listing"},
        )

    @patch("apps.listings.serializers.upload_listing_image")
    def test_farmer_can_upload_listing_images(self, upload_listing_image):
        upload_listing_image.side_effect = [
            "https://res.cloudinary.com/demo/image/upload/listings/maize1.jpg",
            "https://res.cloudinary.com/demo/image/upload/listings/maize2.jpg",
        ]
        area = AdmArea.objects.create(name="Morogoro", level="region")
        image_content = (
            b"\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00"
            b"\x00\x00\x00\xff\xff\xff\x21\xf9\x04\x01\x00\x00\x00"
            b"\x00\x2c\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02"
            b"\x44\x01\x00\x3b"
        )
        image_1 = SimpleUploadedFile("maize1.gif", image_content, content_type="image/gif")
        image_2 = SimpleUploadedFile("maize2.gif", image_content, content_type="image/gif")

        self.client.force_authenticate(self.farmer)
        response = self.client.post(
            "/api/v1/listings",
            {
                "commodity_id": self.commodity.public_id,
                "adm_area_id": area.public_id,
                "title": "Fresh maize harvest",
                "description": "50 bags of premium maize",
                "price": "5000.00",
                "quantity": "50.00",
                "images_upload": [image_1, image_2],
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(upload_listing_image.call_count, 2)
        self.assertEqual(len(response.data["data"]["images"]), 2)
        self.assertEqual(
            response.data["data"]["images"][0]["image_url"],
            "https://res.cloudinary.com/demo/image/upload/listings/maize1.jpg",
        )
        self.assertTrue(response.data["data"]["images"][0]["is_primary"])
