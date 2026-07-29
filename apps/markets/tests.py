from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.areas.models import AdmArea
from apps.commodities.models import Commodity
from apps.markets.models import Market, MarketCommodityPrice


class MarketCommodityPriceUniquenessTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username="market-officer",
            email="market-officer@example.com",
            password="password",
            is_staff=True,
        )
        self.area = AdmArea.objects.create(name="Kampala", level=AdmArea.Level.REGION)
        self.market = Market.objects.create(
            name="Owino Market",
            admin_area=self.area,
            created_by=self.user,
        )
        self.other_market = Market.objects.create(
            name="Nakasero Market",
            admin_area=self.area,
            created_by=self.user,
        )
        self.commodity = Commodity.objects.create(name="Maize", unit="kg")
        self.price_date = date(2026, 7, 28)
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def create_price(self, **overrides):
        values = {
            "market": self.market,
            "commodity": self.commodity,
            "pricetype": MarketCommodityPrice.PriceType.RETAIL,
            "price": Decimal("1000.00"),
            "currency": "UGX",
            "price_date": self.price_date,
            "created_by": self.user,
        }
        values.update(overrides)
        return MarketCommodityPrice.objects.create(**values)

    def test_database_rejects_duplicate_active_price_for_same_market_commodity_and_date(self):
        self.create_price()

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self.create_price(price=Decimal("1200.00"))

    def test_database_allows_recreating_price_after_soft_delete(self):
        price = self.create_price()
        price.deleted_at = timezone.now()
        price.save(update_fields=["deleted_at", "updated_at"])

        replacement = self.create_price(price=Decimal("1200.00"))

        self.assertEqual(replacement.market, self.market)
        self.assertEqual(replacement.commodity, self.commodity)
        self.assertEqual(replacement.price_date, self.price_date)

    def test_api_rejects_duplicate_price_create(self):
        self.create_price()

        response = self.client.post(
            reverse("markets:market-price-list"),
            {
                "market_id": self.market.public_id,
                "commodity_id": self.commodity.public_id,
                "pricetype": MarketCommodityPrice.PriceType.RETAIL,
                "price": "1200.00",
                "currency": "UGX",
                "price_date": self.price_date.isoformat(),
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("already exists", str(response.data))

    def test_database_allows_different_price_types_for_same_market_commodity_and_date(self):
        self.create_price(pricetype=MarketCommodityPrice.PriceType.RETAIL)

        wholesale_price = self.create_price(
            pricetype=MarketCommodityPrice.PriceType.WHOLESALE,
            price=Decimal("1200.00"),
        )

        self.assertEqual(wholesale_price.pricetype, MarketCommodityPrice.PriceType.WHOLESALE)

    def test_api_rejects_update_to_existing_market_commodity_date_combination(self):
        existing_price = self.create_price()
        price_to_update = self.create_price(
            market=self.other_market,
            price=Decimal("1500.00"),
        )

        response = self.client.patch(
            reverse("markets:market-price-detail", args=[price_to_update.public_id]),
            {
                "market_id": existing_price.market.public_id,
                "commodity_id": existing_price.commodity.public_id,
                "pricetype": existing_price.pricetype,
                "price_date": existing_price.price_date.isoformat(),
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("already exists", str(response.data))
