from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.auth.models import Profile

from .models import Commodity, CommodityCategory, Market


class CommodityApiTests(APITestCase):
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

    def test_admin_can_create_category_and_commodity(self):
        category_response = self.client.post(
            "/api/v1/commodities/categories/",
            {"name": "Cereals", "description": "Grain crops"},
            format="json",
        )

        self.assertEqual(category_response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(category_response.data["success"])
        category_id = category_response.data["data"]["category_id"]
        self.assertRegex(category_id, r"^[1-9BCDFGHJKLMNPQRSTVWXYZbcdfghjkmnpqrstvwxyz]{10}$")
        self.assertNotIn("id", category_response.data["data"])

        commodity_response = self.client.post(
            "/api/v1/commodities/",
            {
                "name": "Maize",
                "unit": "kg",
                "description": "Dry maize grain",
                "category_ids": [category_id],
            },
            format="json",
        )

        self.assertEqual(commodity_response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(commodity_response.data["success"])
        self.assertEqual(commodity_response.data["data"]["name"], "Maize")
        self.assertEqual(commodity_response.data["data"]["categories"][0]["category_id"], category_id)
        self.assertRegex(commodity_response.data["data"]["commodity_id"], r"^[1-9BCDFGHJKLMNPQRSTVWXYZbcdfghjkmnpqrstvwxyz]{10}$")
        self.assertNotIn("id", commodity_response.data["data"])

    def test_authenticated_user_can_list_and_get_commodities(self):
        user = get_user_model().objects.create_user(
            username="farmer",
            email="farmer@example.com",
            password="StrongPass123",
        )
        Profile.objects.create(user=user, role=Profile.Role.FARMER)
        category = CommodityCategory.objects.create(name="Vegetables")
        commodity = Commodity.objects.create(name="Tomato", unit="crate")
        commodity.categories.add(category)
        self.client.force_authenticate(user)

        list_response = self.client.get("/api/v1/commodities/")
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertTrue(list_response.data["success"])
        commodity_ids = [item["commodity_id"] for item in list_response.data["data"]]
        self.assertIn(commodity.public_id, commodity_ids)

        detail_response = self.client.get(f"/api/v1/commodities/{commodity.public_id}/")
        self.assertEqual(detail_response.status_code, status.HTTP_200_OK)
        self.assertEqual(detail_response.data["data"]["name"], "Tomato")

    def test_non_admin_cannot_create_commodity(self):
        user = get_user_model().objects.create_user(
            username="buyer",
            email="buyer@example.com",
            password="StrongPass123",
        )
        Profile.objects.create(user=user, role=Profile.Role.BUYER)
        self.client.force_authenticate(user)

        response = self.client.post(
            "/api/v1/commodities/",
            {"name": "Rice", "unit": "kg"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(response.data["success"])

    def test_admin_can_update_and_delete_commodity(self):
        category = CommodityCategory.objects.create(name="Fruits")
        commodity = Commodity.objects.create(name="Mango", unit="piece")
        commodity.categories.add(category)

        update_response = self.client.patch(
            f"/api/v1/commodities/{commodity.public_id}/",
            {"unit": "basket", "category_ids": []},
            format="json",
        )
        self.assertEqual(update_response.status_code, status.HTTP_200_OK)
        self.assertEqual(update_response.data["data"]["unit"], "basket")
        self.assertEqual(update_response.data["data"]["categories"], [])

        delete_response = self.client.delete(f"/api/v1/commodities/{commodity.public_id}/")
        self.assertEqual(delete_response.status_code, status.HTTP_200_OK)
        self.assertFalse(Commodity.objects.filter(public_id=commodity.public_id).exists())

    def test_prediction_markets_are_seeded(self):
        market_names = list(Market.objects.filter(is_active=True).values_list("name", flat=True))
        self.assertIn("Ifakara Central Market", market_names)
        self.assertIn("Morogoro Central Market", market_names)

    def test_prediction_commodities_are_seeded(self):
        commodity_names = list(Commodity.objects.filter(name__in=["Beans", "Rice"]).values_list("name", flat=True))
        self.assertIn("Beans", commodity_names)
        self.assertIn("Rice", commodity_names)
