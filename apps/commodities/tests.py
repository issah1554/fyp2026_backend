from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.auth.models import Profile
from apps.users.models import Role

from .models import Commodity, CommodityCategory, CommodityUnit


class CommodityApiTests(APITestCase):
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

    def test_admin_can_create_category_and_commodity(self):
        category_response = self.client.post(
            "/api/v1/commodities/categories",
            {"name": "Cereals", "description": "Grain crops"},
            format="json",
        )

        self.assertEqual(category_response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(category_response.data["success"])
        category_id = category_response.data["data"]["category_id"]
        self.assertRegex(category_id, r"^[1-9BCDFGHJKLMNPQRSTVWXYZbcdfghjkmnpqrstvwxyz]{10}$")
        self.assertNotIn("id", category_response.data["data"])

        commodity_response = self.client.post(
            "/api/v1/commodities",
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

    def test_admin_can_manage_units_and_assign_unit_to_commodity(self):
        unit_response = self.client.post(
            "/api/v1/commodities/units",
            {"name": "Kilogram", "symbol": "Kg", "description": "Weight in kilograms"},
            format="json",
        )
        self.assertEqual(unit_response.status_code, status.HTTP_201_CREATED)
        unit_id = unit_response.data["data"]["unit_id"]
        self.assertRegex(unit_id, r"^[1-9BCDFGHJKLMNPQRSTVWXYZbcdfghjkmnpqrstvwxyz]{10}$")

        commodity_response = self.client.post(
            "/api/v1/commodities",
            {
                "name": "Rice",
                "unit_id": unit_id,
                "description": "Milled rice",
            },
            format="json",
        )
        self.assertEqual(commodity_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(commodity_response.data["data"]["unit"], "Kg")
        self.assertEqual(commodity_response.data["data"]["unit_detail"]["unit_id"], unit_id)

        update_response = self.client.patch(
            f"/api/v1/commodities/units/{unit_id}",
            {"symbol": "kg"},
            format="json",
        )
        self.assertEqual(update_response.status_code, status.HTTP_200_OK)
        self.assertEqual(update_response.data["data"]["symbol"], "kg")

        list_response = self.client.get("/api/v1/commodities/units")
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertTrue(any(x["unit_id"] == unit_id for x in list_response.data["data"]))

    def test_authenticated_user_can_list_and_get_commodities(self):
        user = get_user_model().objects.create_user(
            username="farmer",
            email="farmer@example.com",
            password="StrongPass123",
        )
        Profile.objects.create(user=user, role=Role.objects.get(code=Profile.Role.FARMER))
        category = CommodityCategory.objects.create(name="Vegetables")
        commodity = Commodity.objects.create(name="Tomato", unit="crate")
        commodity.categories.add(category)
        self.client.force_authenticate(user)

        list_response = self.client.get("/api/v1/commodities")
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertTrue(list_response.data["success"])
        self.assertEqual(list_response.data["data"][0]["commodity_id"], commodity.public_id)

        detail_response = self.client.get(f"/api/v1/commodities/{commodity.public_id}")
        self.assertEqual(detail_response.status_code, status.HTTP_200_OK)
        self.assertEqual(detail_response.data["data"]["name"], "Tomato")

    def test_non_admin_cannot_create_commodity(self):
        user = get_user_model().objects.create_user(
            username="buyer",
            email="buyer@example.com",
            password="StrongPass123",
        )
        Profile.objects.create(user=user, role=Role.objects.get(code=Profile.Role.BUYER))
        self.client.force_authenticate(user)

        response = self.client.post(
            "/api/v1/commodities",
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
            f"/api/v1/commodities/{commodity.public_id}",
            {"unit": "basket", "category_ids": []},
            format="json",
        )
        self.assertEqual(update_response.status_code, status.HTTP_200_OK)
        self.assertEqual(update_response.data["data"]["unit"], "basket")
        self.assertEqual(update_response.data["data"]["categories"], [])

        delete_response = self.client.delete(f"/api/v1/commodities/{commodity.public_id}")
        self.assertEqual(delete_response.status_code, status.HTTP_200_OK)
        self.assertFalse(Commodity.objects.filter(public_id=commodity.public_id).exists())

    def test_commodity_list_is_paginated_with_totals(self):
        category = CommodityCategory.objects.create(name="Cereals")
        for index in range(12):
            commodity = Commodity.objects.create(name=f"Commodity {index:02d}", unit="kg")
            if index < 8:
                commodity.categories.add(category)

        response = self.client.get("/api/v1/commodities", {"page": 2, "page_size": 5})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["data"]), 5)
        self.assertEqual(response.data["meta"]["pagination"]["page"], 2)
        self.assertEqual(response.data["meta"]["pagination"]["page_size"], 5)
        self.assertEqual(response.data["meta"]["pagination"]["total_items"], 12)
        self.assertEqual(response.data["meta"]["pagination"]["total_pages"], 3)
        self.assertEqual(response.data["meta"]["totals"]["total"], 12)
        self.assertEqual(response.data["meta"]["totals"]["categories"], 1)
        self.assertEqual(response.data["meta"]["totals"]["categorized"], 8)
        self.assertEqual(response.data["meta"]["totals"]["uncategorized"], 4)

    def test_commodity_list_filters_by_search_and_category(self):
        cereals = CommodityCategory.objects.create(name="Cereals")
        vegetables = CommodityCategory.objects.create(name="Vegetables")
        maize = Commodity.objects.create(name="Maize", unit="kg")
        maize.categories.add(cereals)
        tomato = Commodity.objects.create(name="Tomato", unit="crate")
        tomato.categories.add(vegetables)

        category_response = self.client.get("/api/v1/commodities", {"category_id": cereals.public_id})
        self.assertEqual(category_response.status_code, status.HTTP_200_OK)
        self.assertTrue(any(x["name"] == "Maize" for x in category_response.data["data"]))
        self.assertFalse(any(x["name"] == "Tomato" for x in category_response.data["data"]))

        search_response = self.client.get("/api/v1/commodities", {"search": "tom"})
        self.assertEqual(search_response.status_code, status.HTTP_200_OK)
        self.assertTrue(any(x["name"] == "Tomato" for x in search_response.data["data"]))
        self.assertFalse(any(x["name"] == "Maize" for x in search_response.data["data"]))
