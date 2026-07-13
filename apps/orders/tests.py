from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.auth.models import Profile
from apps.areas.models import AdmArea
from apps.commodities.models import Commodity
from apps.listings.models import CommodityListing
from .models import Order


class OrdersApiTests(APITestCase):
    def setUp(self):
        # Create users
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

        self.buyer = get_user_model().objects.create_user(
            username="buyer",
            email="buyer@example.com",
            password="StrongPass123",
        )
        Profile.objects.create(
            user=self.buyer,
            role=Profile.Role.BUYER,
            email_verified_at=timezone.now(),
        )

        self.other_user = get_user_model().objects.create_user(
            username="other",
            email="other@example.com",
            password="StrongPass123",
        )
        Profile.objects.create(
            user=self.other_user,
            role=Profile.Role.BUYER,
            email_verified_at=timezone.now(),
        )

        # Create commodity, area, and listing
        self.commodity = Commodity.objects.create(name="Rice", unit="kg", description="Premium Basmati")
        self.area = AdmArea.objects.create(name="Mbeya", level="region")
        
        self.listing = CommodityListing.objects.create(
            commodity=self.commodity,
            adm_area=self.area,
            user=self.farmer,
            title="Premium Rice Harvest",
            price="3000.00",
            quantity="100.00",
            status="active"
        )

    def test_buyer_can_place_order_and_deduct_quantity(self):
        self.client.force_authenticate(self.buyer)
        
        # Place order
        create_response = self.client.post(
            "/api/v1/orders/",
            {
                "listing_id": self.listing.public_id,
                "quantity": "20.00",
            },
            format="json",
        )
        
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(create_response.data["success"])
        order_id = create_response.data["data"]["order_id"]
        
        # Validate total price calculation (3000.00 * 20.00 = 60000.00)
        self.assertEqual(create_response.data["data"]["total_price"], "60000.00")
        
        # Validate that the quantity has been deducted from the listing
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.quantity, 80.00)

        # Verify participant permissions
        # Buyer should be able to view details
        detail_response = self.client.get(f"/api/v1/orders/{order_id}/")
        self.assertEqual(detail_response.status_code, status.HTTP_200_OK)

        # Seller (farmer) should be able to view details
        self.client.force_authenticate(self.farmer)
        seller_detail_response = self.client.get(f"/api/v1/orders/{order_id}/")
        self.assertEqual(seller_detail_response.status_code, status.HTTP_200_OK)

        # Unrelated user should NOT be able to view details
        self.client.force_authenticate(self.other_user)
        other_detail_response = self.client.get(f"/api/v1/orders/{order_id}/")
        self.assertEqual(other_detail_response.status_code, status.HTTP_403_FORBIDDEN)

    def test_order_fails_if_quantity_exceeds_available(self):
        self.client.force_authenticate(self.buyer)
        
        # Attempt to place order for 120 (available is 100)
        create_response = self.client.post(
            "/api/v1/orders/",
            {
                "listing_id": self.listing.public_id,
                "quantity": "120.00",
            },
            format="json",
        )
        
        self.assertEqual(create_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(create_response.data["success"])
        self.assertIn("quantity", create_response.data["errors"])
