from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.auth.models import Profile
from apps.users.models import Role

from .models import Commodity, CommodityCategory, CommodityUnit, CommodityUnitMap


class CommodityApiTests(APITestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_user(
            username="admin",
            email="admin@example.com",
            password="StrongPass123",
            is_staff=True,
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
                # unit is now M2M — no raw "unit" or "description" field
                "category_ids": [category_id],
            },
            format="json",
        )

        self.assertEqual(commodity_response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(commodity_response.data["success"])
        self.assertEqual(commodity_response.data["data"]["name"], "Maize")
        self.assertEqual(commodity_response.data["data"]["categories"][0]["category_id"], category_id)
        self.assertRegex(
            commodity_response.data["data"]["commodity_id"],
            r"^[1-9BCDFGHJKLMNPQRSTVWXYZbcdfghjkmnpqrstvwxyz]{10}$",
        )
        self.assertNotIn("id", commodity_response.data["data"])
        # description field no longer in response
        self.assertNotIn("description", commodity_response.data["data"])

    def test_admin_can_manage_units_and_assign_unit_to_commodity(self):
        # Create a unit — description is no longer accepted/returned
        unit_response = self.client.post(
            "/api/v1/commodities/units",
            {"name": "Kilogram", "symbol": "Kg"},
            format="json",
        )
        self.assertEqual(unit_response.status_code, status.HTTP_201_CREATED)
        unit_id = unit_response.data["data"]["unit_id"]
        self.assertRegex(unit_id, r"^[1-9BCDFGHJKLMNPQRSTVWXYZbcdfghjkmnpqrstvwxyz]{10}$")
        # description no longer in unit response
        self.assertNotIn("description", unit_response.data["data"])

        # Create commodity and assign primary unit via unit_id
        commodity_response = self.client.post(
            "/api/v1/commodities",
            {
                "name": "Rice",
                "unit_id": unit_id,
            },
            format="json",
        )
        self.assertEqual(commodity_response.status_code, status.HTTP_201_CREATED)
        # Backward-compatible: 'unit' still returns the primary unit's symbol
        self.assertEqual(commodity_response.data["data"]["unit"], "Kg")
        # Backward-compatible: 'unit_detail' still returns the primary unit object
        self.assertEqual(commodity_response.data["data"]["unit_detail"]["unit_id"], unit_id)
        # New: 'units' returns the full list
        self.assertEqual(len(commodity_response.data["data"]["units"]), 1)
        self.assertEqual(commodity_response.data["data"]["units"][0]["unit_id"], unit_id)

        # Update unit symbol
        update_response = self.client.patch(
            f"/api/v1/commodities/units/{unit_id}",
            {"symbol": "kg"},
            format="json",
        )
        self.assertEqual(update_response.status_code, status.HTTP_200_OK)
        self.assertEqual(update_response.data["data"]["symbol"], "kg")

        # List units
        list_response = self.client.get("/api/v1/commodities/units")
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertTrue(any(x["unit_id"] == unit_id for x in list_response.data["data"]))

    def test_admin_can_assign_multiple_units_to_commodity(self):
        kg = CommodityUnit.objects.create(name="Kilogram", symbol="kg")
        bag = CommodityUnit.objects.create(name="Bag (90kg)", symbol="bag")

        # Assign primary unit via unit_id and additional via unit_ids
        commodity_response = self.client.post(
            "/api/v1/commodities",
            {
                "name": "Maize",
                "unit_id": kg.public_id,
                "unit_ids": [bag.public_id],
            },
            format="json",
        )
        self.assertEqual(commodity_response.status_code, status.HTTP_201_CREATED)
        data = commodity_response.data["data"]
        # Primary unit exposed as backward-compat 'unit' string
        self.assertEqual(data["unit"], "kg")
        # Both units in the 'units' list
        unit_symbols = {u["symbol"] for u in data["units"]}
        self.assertIn("kg", unit_symbols)
        self.assertIn("bag", unit_symbols)
        self.assertEqual(len(data["units"]), 2)

    def test_public_user_can_list_and_get_commodities(self):
        category = CommodityCategory.objects.create(name="Vegetables")
        commodity = Commodity.objects.create(name="Tomato")
        commodity.categories.add(category)
        self.client.force_authenticate(user=None)

        list_response = self.client.get("/api/v1/commodities")
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertTrue(list_response.data["success"])
        commodity_ids = [item["commodity_id"] for item in list_response.data["data"]]
        self.assertIn(commodity.public_id, commodity_ids)

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
            {"name": "Rice"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(response.data["success"])

    def test_admin_can_update_and_delete_commodity(self):
        category = CommodityCategory.objects.create(name="Fruits")
        kg = CommodityUnit.objects.create(name="Kilogram", symbol="kg")
        commodity = Commodity.objects.create(name="Mango")
        commodity.categories.add(category)
        CommodityUnitMap.objects.create(commodity=commodity, unit=kg, is_primary=True)

        # Update unit via unit_id (change primary unit)
        bag = CommodityUnit.objects.create(name="Basket", symbol="basket")
        update_response = self.client.patch(
            f"/api/v1/commodities/{commodity.public_id}",
            {"unit_id": bag.public_id, "category_ids": []},
            format="json",
        )
        self.assertEqual(update_response.status_code, status.HTTP_200_OK)
        # The new primary unit's symbol should be returned in 'unit'
        self.assertEqual(update_response.data["data"]["unit"], "basket")
        self.assertEqual(update_response.data["data"]["categories"], [])

        delete_response = self.client.delete(f"/api/v1/commodities/{commodity.public_id}")
        self.assertEqual(delete_response.status_code, status.HTTP_200_OK)
        self.assertFalse(Commodity.objects.filter(public_id=commodity.public_id).exists())

    def test_commodity_list_is_paginated_with_totals(self):
        Commodity.objects.all().delete()
        category = CommodityCategory.objects.create(name="Cereals")
        for index in range(12):
            commodity = Commodity.objects.create(name=f"Commodity {index:02d}")
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
        maize = Commodity.objects.create(name="Maize")
        maize.categories.add(cereals)
        tomato = Commodity.objects.create(name="Tomato")
        tomato.categories.add(vegetables)

        category_response = self.client.get("/api/v1/commodities", {"category_id": cereals.public_id})
        self.assertEqual(category_response.status_code, status.HTTP_200_OK)
        self.assertTrue(any(x["name"] == "Maize" for x in category_response.data["data"]))
        self.assertFalse(any(x["name"] == "Tomato" for x in category_response.data["data"]))

        search_response = self.client.get("/api/v1/commodities", {"search": "tom"})
        self.assertEqual(search_response.status_code, status.HTTP_200_OK)
        self.assertTrue(any(x["name"] == "Tomato" for x in search_response.data["data"]))
        self.assertFalse(any(x["name"] == "Maize" for x in search_response.data["data"]))

    def test_prediction_commodities_are_seeded(self):
        commodity_names = list(
            Commodity.objects.filter(name__in=["Beans", "Rice"]).values_list("name", flat=True)
        )
        self.assertIn("Beans", commodity_names)
        self.assertIn("Rice", commodity_names)
