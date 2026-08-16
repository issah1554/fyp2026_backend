import math
import random
from collections import defaultdict
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Avg, Case, DateTimeField, Value, When
from django.utils import timezone

from apps.areas.models import AdmArea
from apps.auth.models import Profile
from apps.commodities.models import Commodity
from apps.common.ids import generate_public_id
from apps.listings.models import CommodityListing
from apps.markets.models import MarketCommodityPrice
from apps.orders.models import Order


MARKER = "[SYNTH_ARCHIVE_V1]"
START_DATE = date(2024, 7, 1)
END_DATE = date(2026, 7, 17)

ORDER_TARGETS = {
    "Maize": 18000,
    "Rice": 16000,
    "Beans": 14000,
    "Irish Potatoes": 12000,
    "Sorghum": 9000,
    "Wheat Grain": 8000,
    "Finger Millet": 7000,
    "Bulrush Millet": 6000,
    "Coffee": 5000,
    "Cocoa": 5000,
}

LISTING_TARGETS = {
    "Maize": 900,
    "Rice": 800,
    "Beans": 700,
    "Irish Potatoes": 600,
    "Sorghum": 450,
    "Wheat Grain": 400,
    "Finger Millet": 350,
    "Bulrush Millet": 300,
    "Coffee": 250,
    "Cocoa": 250,
}

QUANTITY_PROFILES = {
    "Maize": (100, 5000),
    "Rice": (50, 3000),
    "Beans": (25, 2000),
    "Irish Potatoes": (50, 4000),
    "Sorghum": (100, 3000),
    "Wheat Grain": (100, 5000),
    "Finger Millet": (25, 1500),
    "Bulrush Millet": (25, 1500),
    "Coffee": (10, 1000),
    "Cocoa": (10, 800),
}

BASE_PRICES = {
    "Maize": Decimal("850.00"),
    "Rice": Decimal("2550.00"),
    "Beans": Decimal("2600.00"),
    "Irish Potatoes": Decimal("1300.00"),
    "Sorghum": Decimal("920.00"),
    "Wheat Grain": Decimal("1600.00"),
    "Finger Millet": Decimal("1800.00"),
    "Bulrush Millet": Decimal("1250.00"),
    "Coffee": Decimal("13800.00"),
    "Cocoa": Decimal("8500.00"),
}

SEASONAL_WEIGHTS = {
    "Maize": [1.05, 1.0, 1.1, 1.25, 1.35, 1.25, 1.1, 0.95, 0.9, 0.95, 1.0, 1.1],
    "Rice": [1.15, 1.0, 0.95, 0.95, 1.0, 1.05, 1.0, 0.95, 1.0, 1.05, 1.15, 1.25],
    "Beans": [1.05, 1.0, 1.1, 1.15, 1.2, 1.15, 1.0, 0.9, 0.9, 0.95, 1.0, 1.1],
    "Irish Potatoes": [1.0, 1.05, 1.1, 1.0, 0.95, 0.9, 0.95, 1.1, 1.2, 1.15, 1.05, 1.0],
    "Sorghum": [0.95, 0.95, 1.0, 1.15, 1.25, 1.2, 1.05, 0.95, 0.9, 0.95, 1.0, 1.05],
    "Wheat Grain": [1.0, 1.0, 1.05, 1.1, 1.15, 1.1, 1.0, 0.95, 0.95, 1.0, 1.05, 1.1],
    "Finger Millet": [0.95, 0.95, 1.05, 1.15, 1.2, 1.15, 1.05, 0.95, 0.9, 0.95, 1.0, 1.05],
    "Bulrush Millet": [0.95, 0.95, 1.0, 1.15, 1.2, 1.15, 1.05, 0.95, 0.9, 0.95, 1.0, 1.05],
    "Coffee": [1.1, 1.05, 1.0, 0.95, 0.95, 1.0, 1.1, 1.2, 1.2, 1.1, 1.0, 1.05],
    "Cocoa": [1.05, 1.0, 0.95, 0.95, 1.0, 1.1, 1.2, 1.2, 1.1, 1.0, 0.95, 1.0],
}


class Command(BaseCommand):
    help = "Seed realistic synthetic archived listings and orders fitted to historical commodity prices."

    def add_arguments(self, parser):
        parser.add_argument("--clear-existing", action="store_true")
        parser.add_argument("--seed", type=int, default=20260816)
        parser.add_argument("--batch-size", type=int, default=5000)

    def handle(self, *args, **options):
        random.seed(options["seed"])
        batch_size = options["batch_size"]

        commodities = {
            commodity.name: commodity
            for commodity in Commodity.objects.filter(name__in=ORDER_TARGETS.keys())
        }
        missing = sorted(set(ORDER_TARGETS) - set(commodities))
        if missing:
            raise CommandError(f"Missing required commodities: {', '.join(missing)}")

        sellers, buyers = self._get_users()
        if not sellers or not buyers:
            raise CommandError("Need at least one seller and one buyer user.")

        price_rows = self._load_price_rows(commodities)
        if not price_rows:
            raise CommandError("No matching historical market price records found.")

        used_listing_ids = set(CommodityListing.objects.values_list("public_id", flat=True))
        used_order_ids = set(Order.objects.values_list("public_id", flat=True))

        with transaction.atomic():
            if options["clear_existing"]:
                self._clear_existing()

            listings_by_commodity = self._create_listings(
                commodities=commodities,
                sellers=sellers,
                price_rows=price_rows,
                used_ids=used_listing_ids,
                batch_size=batch_size,
            )
            self._create_orders(
                listings_by_commodity=listings_by_commodity,
                buyers=buyers,
                used_ids=used_order_ids,
                batch_size=batch_size,
            )

        self.stdout.write(self.style.SUCCESS("Synthetic archived demand data created."))

    def _get_users(self):
        User = get_user_model()
        sellers = list(
            User.objects.filter(
                profile__roles__code__in=[Profile.Role.FARMER, Profile.Role.ENTREPRENEUR]
            ).distinct()
        )
        buyers = list(
            User.objects.filter(
                profile__roles__code__in=[
                    Profile.Role.BUYER,
                    Profile.Role.ENTREPRENEUR,
                    Profile.Role.ADMIN,
                    Profile.Role.MARKET_OFFICER,
                ]
            ).distinct()
        )
        fallback = list(User.objects.all())
        return sellers or fallback, buyers or fallback

    def _load_price_rows(self, commodities):
        avg_prices = {
            row["commodity_id"]: row["avg_price"]
            for row in MarketCommodityPrice.objects.filter(
                commodity_id__in=[commodity.id for commodity in commodities.values()],
                price_date__range=(START_DATE, END_DATE),
                deleted_at__isnull=True,
            )
            .values("commodity_id")
            .annotate(avg_price=Avg("price"))
        }
        rows = defaultdict(list)
        qs = (
            MarketCommodityPrice.objects.filter(
                commodity_id__in=[commodity.id for commodity in commodities.values()],
                price_date__range=(START_DATE, END_DATE),
                deleted_at__isnull=True,
            )
            .select_related("commodity", "market__admin_area")
            .only("commodity_id", "commodity__name", "market__admin_area_id", "price", "price_date")
            .order_by("commodity__name", "price_date")
        )
        for row in qs.iterator(chunk_size=5000):
            avg_price = avg_prices.get(row.commodity_id) or row.price
            rows[row.commodity.name].append(
                {
                    "date": row.price_date,
                    "price": row.price,
                    "area_id": row.market.admin_area_id,
                    "avg_price": avg_price,
                }
            )
        self._fill_missing_price_rows(rows)
        return rows

    def _fill_missing_price_rows(self, rows):
        missing_commodities = [
            commodity_name
            for commodity_name in BASE_PRICES
            if not rows.get(commodity_name)
        ]
        if not missing_commodities:
            return

        priced_area_ids = list(
            MarketCommodityPrice.objects.filter(
                price_date__range=(START_DATE, END_DATE),
                deleted_at__isnull=True,
            )
            .values_list("market__admin_area_id", flat=True)
            .distinct()
        )
        area_ids = priced_area_ids or list(AdmArea.objects.values_list("id", flat=True)[:25])
        if not area_ids:
            raise CommandError("No administrative areas available for synthetic price fallback.")

        current = START_DATE
        while current <= END_DATE:
            for commodity_name in missing_commodities:
                base_price = BASE_PRICES[commodity_name]
                seasonal = Decimal(str(SEASONAL_WEIGHTS[commodity_name][current.month - 1]))
                trend = Decimal("1.00") + Decimal(str(((current - START_DATE).days / 365) * 0.035))
                noise = Decimal(str(random.uniform(0.92, 1.10)))
                price = self._money(base_price * seasonal * trend * noise)
                rows[commodity_name].append(
                    {
                        "date": current,
                        "price": price,
                        "area_id": random.choice(area_ids),
                        "avg_price": base_price,
                    }
                )
            current += timedelta(days=7)

    def _clear_existing(self):
        listings = CommodityListing.objects.filter(title__startswith=MARKER)
        deleted_orders, _ = Order.objects.filter(listing__in=listings).delete()
        deleted_listings, _ = listings.delete()
        self.stdout.write(f"Cleared {deleted_orders} synthetic orders and {deleted_listings} synthetic listings.")

    def _create_listings(self, commodities, sellers, price_rows, used_ids, batch_size):
        listings_by_commodity = defaultdict(list)
        pending = []
        created_at_by_public_id = {}
        for commodity_name, target in LISTING_TARGETS.items():
            commodity = commodities[commodity_name]
            samples = price_rows[commodity_name]
            for index in range(target):
                price_sample = self._weighted_price_sample(samples, commodity_name)
                created_at = self._datetime_on(price_sample["date"] - timedelta(days=random.randint(1, 21)))
                public_id = self._new_public_id(used_ids)
                quantity = self._listing_quantity(commodity_name)
                listing = CommodityListing(
                    public_id=public_id,
                    commodity=commodity,
                    adm_area_id=price_sample["area_id"],
                    user=random.choice(sellers),
                    title=f"{MARKER} {commodity_name} archived lot {index + 1}",
                    description=(
                        f"Synthetic archived {commodity_name} listing generated from historical "
                        "market price data for demand forecasting experiments."
                    ),
                    price=self._money(price_sample["price"] * Decimal(str(random.uniform(0.95, 1.12)))),
                    quantity=quantity,
                    status=random.choices(
                        [
                            CommodityListing.Status.SOLD_OUT,
                            CommodityListing.Status.ARCHIVED,
                            CommodityListing.Status.AVAILABLE,
                        ],
                        weights=[60, 30, 10],
                        k=1,
                    )[0],
                    created_at=created_at,
                )
                pending.append(listing)
                listings_by_commodity[commodity_name].append(listing)
                created_at_by_public_id[public_id] = created_at
                if len(pending) >= batch_size:
                    CommodityListing.objects.bulk_create(pending, batch_size=batch_size)
                    pending = []
        if pending:
            CommodityListing.objects.bulk_create(pending, batch_size=batch_size)

        self._bulk_update_created_at(CommodityListing, created_at_by_public_id, batch_size)
        stored = defaultdict(list)
        for listing in (
            CommodityListing.objects.filter(title__startswith=MARKER)
            .select_related("commodity")
            .order_by("commodity__name", "public_id")
        ):
            stored[listing.commodity.name].append(listing)
        self.stdout.write(f"Created {sum(len(items) for items in stored.values())} synthetic listings.")
        return stored

    def _create_orders(self, listings_by_commodity, buyers, used_ids, batch_size):
        pending = []
        created_at_by_public_id = {}
        status_choices = ["completed", "confirmed", "shipped", "pending", "cancelled"]
        status_weights = [70, 15, 8, 4, 3]
        for commodity_name, target in ORDER_TARGETS.items():
            listings = listings_by_commodity[commodity_name]
            allocations = self._allocate_orders(len(listings), target)
            for listing, order_count in zip(listings, allocations):
                remaining = listing.quantity or self._listing_quantity(commodity_name)
                for _index in range(order_count):
                    status = random.choices(status_choices, weights=status_weights, k=1)[0]
                    quantity = self._order_quantity(commodity_name)
                    if status in {"completed", "confirmed", "shipped"}:
                        quantity = min(quantity, max(Decimal("1.00"), remaining * Decimal("0.35")))
                        remaining = max(Decimal("0.00"), remaining - quantity)
                    created_at = self._order_datetime(listing.created_at)
                    public_id = self._new_public_id(used_ids)
                    order = Order(
                        public_id=public_id,
                        listing=listing,
                        user=random.choice([buyer for buyer in buyers if buyer.id != listing.user_id] or buyers),
                        quantity=quantity,
                        total_price=self._money(quantity * listing.price),
                        status=status,
                        created_at=created_at,
                    )
                    pending.append(order)
                    created_at_by_public_id[public_id] = created_at
                    if len(pending) >= batch_size:
                        Order.objects.bulk_create(pending, batch_size=batch_size)
                        pending = []
        if pending:
            Order.objects.bulk_create(pending, batch_size=batch_size)
        self._bulk_update_created_at(Order, created_at_by_public_id, batch_size)
        self.stdout.write(f"Created {sum(ORDER_TARGETS.values())} synthetic orders.")

    def _bulk_update_created_at(self, model, created_at_by_public_id, batch_size):
        items = list(created_at_by_public_id.items())
        for start in range(0, len(items), batch_size):
            batch = items[start : start + batch_size]
            model.objects.filter(public_id__in=[public_id for public_id, _created_at in batch]).update(
                created_at=Case(
                    *[
                        When(public_id=public_id, then=Value(created_at))
                        for public_id, created_at in batch
                    ],
                    output_field=DateTimeField(),
                )
            )

    def _weighted_price_sample(self, samples, commodity_name):
        weights = []
        for sample in samples:
            seasonal = SEASONAL_WEIGHTS[commodity_name][sample["date"].month - 1]
            price_factor = float(sample["avg_price"] / sample["price"]) if sample["price"] else 1.0
            price_factor = min(1.3, max(0.7, price_factor))
            weights.append(seasonal * price_factor)
        return random.choices(samples, weights=weights, k=1)[0]

    def _allocate_orders(self, listing_count, order_count):
        base = order_count // listing_count
        remainder = order_count % listing_count
        allocations = [base] * listing_count
        for index in random.sample(range(listing_count), remainder):
            allocations[index] += 1
        random.shuffle(allocations)
        return allocations

    def _listing_quantity(self, commodity_name):
        low, high = QUANTITY_PROFILES[commodity_name]
        average_orders = ORDER_TARGETS[commodity_name] / LISTING_TARGETS[commodity_name]
        average_quantity = (low + high) / 2
        total = average_orders * average_quantity * random.uniform(0.85, 1.25)
        return Decimal(str(round(total, 2)))

    def _order_quantity(self, commodity_name):
        low, high = QUANTITY_PROFILES[commodity_name]
        # Log-normal gives many small/medium orders and fewer very large orders.
        value = random.lognormvariate(math.log((low + high) / 5), 0.85)
        value = min(high, max(low, value))
        return Decimal(str(round(value, 2)))

    def _order_datetime(self, listing_created_at):
        start = listing_created_at + timedelta(hours=random.randint(12, 72))
        end = min(
            self._datetime_on(END_DATE),
            listing_created_at + timedelta(days=random.randint(7, 75)),
        )
        if end <= start:
            end = start + timedelta(days=1)
        delta_seconds = int((end - start).total_seconds())
        return start + timedelta(seconds=random.randint(0, max(1, delta_seconds)))

    def _datetime_on(self, value):
        value = min(max(value, START_DATE), END_DATE)
        return timezone.make_aware(
            datetime.combine(
                value,
                time(
                    hour=random.randint(6, 20),
                    minute=random.randint(0, 59),
                    second=random.randint(0, 59),
                ),
            )
        )

    def _new_public_id(self, used_ids):
        while True:
            public_id = generate_public_id()
            if public_id not in used_ids:
                used_ids.add(public_id)
                return public_id

    def _money(self, value):
        return Decimal(value).quantize(Decimal("0.01"))
