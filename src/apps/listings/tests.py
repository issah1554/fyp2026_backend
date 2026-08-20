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
                "image_urls": [
                    "http://example.com/maize1.jpg",
                    "http://example.com/maize2.jpg",
                    "http://example.com/maize3.jpg",
                ],
            },
            format="json",
        )
        
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(create_response.data["success"])
        listing_id = create_response.data["data"]["listing_id"]
        self.assertEqual(create_response.data["data"]["seller_id"], self.farmer.profile.public_id)
        self.assertEqual(len(create_response.data["data"]["images"]), 3)
        self.assertTrue(create_response.data["data"]["images"][0]["is_primary"])

        # List listings
        list_response = self.client.get("/api/v1/listings")
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(list_response.data["data"]), 1)
        self.assertIn("pagination", list_response.data["meta"])
        self.assertGreaterEqual(list_response.data["meta"]["pagination"]["total_items"], 1)

        # Update listing
        update_response = self.client.patch(
            f"/api/v1/listings/{listing_id}",
            {
                "price": "4800.00",
                "status": "available"
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

    def test_listings_are_paginated_with_count_meta(self):
        area = AdmArea.objects.create(name="Morogoro", level=AdmArea.Level.REGION)
        for index in range(12):
            CommodityListing.objects.create(
                commodity=self.commodity,
                adm_area=area,
                user=self.farmer,
                title=f"Maize listing {index + 1}",
                price=f"{1000 + index}.00",
            )

        response = self.client.get("/api/v1/listings", {"page": 2, "page_size": 5})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["data"]), 5)
        self.assertEqual(response.data["meta"]["pagination"]["page"], 2)
        self.assertEqual(response.data["meta"]["pagination"]["page_size"], 5)
        self.assertEqual(response.data["meta"]["pagination"]["total_items"], 12)
        self.assertEqual(response.data["meta"]["pagination"]["total_pages"], 3)
        self.assertTrue(response.data["meta"]["pagination"]["has_next"])
        self.assertTrue(response.data["meta"]["pagination"]["has_previous"])
        self.assertEqual(response.data["meta"]["counts"]["total"], 12)

    @patch("apps.listings.serializers.upload_listing_image")
    def test_farmer_can_upload_listing_images(self, upload_listing_image):
        upload_listing_image.side_effect = [
            "https://res.cloudinary.com/demo/image/upload/listings/maize1.jpg",
            "https://res.cloudinary.com/demo/image/upload/listings/maize2.jpg",
            "https://res.cloudinary.com/demo/image/upload/listings/maize3.jpg",
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
        image_3 = SimpleUploadedFile("maize3.gif", image_content, content_type="image/gif")

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
                "images_upload": [image_1, image_2, image_3],
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(upload_listing_image.call_count, 3)
        self.assertEqual(len(response.data["data"]["images"]), 3)
        self.assertEqual(
            response.data["data"]["images"][0]["image_url"],
            "https://res.cloudinary.com/demo/image/upload/listings/maize1.jpg",
        )
        self.assertTrue(response.data["data"]["images"][0]["is_primary"])

    def test_create_listing_requires_at_least_three_images(self):
        area = AdmArea.objects.create(name="Morogoro", level="region")
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
                "image_urls": ["http://example.com/maize1.jpg", "http://example.com/maize2.jpg"],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("images_upload", response.data["errors"])

    @patch("apps.listings.serializers.upload_listing_image")
    def test_farmer_can_add_and_remove_listing_images_individually(self, upload_listing_image):
        upload_listing_image.return_value = "https://res.cloudinary.com/demo/image/upload/listings/maize4.jpg"
        area = AdmArea.objects.create(name="Morogoro", level="region")
        listing = CommodityListing.objects.create(
            commodity=self.commodity,
            adm_area=area,
            user=self.farmer,
            title="Fresh maize harvest",
            price="5000.00",
            quantity="50.00",
        )
        for idx in range(3):
            ListingImage.objects.create(
                listing=listing,
                image_url=f"https://res.cloudinary.com/demo/image/upload/listings/maize{idx}.jpg",
                is_primary=idx == 0,
            )

        image_content = (
            b"\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00"
            b"\x00\x00\x00\xff\xff\xff\x21\xf9\x04\x01\x00\x00\x00"
            b"\x00\x2c\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02"
            b"\x44\x01\x00\x3b"
        )
        image = SimpleUploadedFile("maize4.gif", image_content, content_type="image/gif")

        self.client.force_authenticate(self.farmer)
        add_response = self.client.post(
            f"/api/v1/listings/{listing.public_id}/images",
            {"images_upload": [image]},
            format="multipart",
        )
        self.assertEqual(add_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(listing.images.count(), 4)

        image_id = add_response.data["data"][0]["image_id"]
        delete_response = self.client.delete(f"/api/v1/listings/{listing.public_id}/images/{image_id}")
        self.assertEqual(delete_response.status_code, status.HTTP_200_OK)
        self.assertEqual(listing.images.count(), 3)

        remaining_image = listing.images.first()
        blocked_response = self.client.delete(f"/api/v1/listings/{listing.public_id}/images/{remaining_image.public_id}")
        self.assertEqual(blocked_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(listing.images.count(), 3)
