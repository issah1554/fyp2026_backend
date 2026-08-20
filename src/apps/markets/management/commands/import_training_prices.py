import csv
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from apps.areas.models import AdmArea
from apps.commodities.models import Commodity, CommodityCategory, CommodityCategoryMap, CommodityUnit, CommodityUnitMap
from apps.common.ids import generate_public_id
from apps.markets.models import Market, MarketCommodityPrice


class Command(BaseCommand):
    help = "Import historical training price data from CSV into MarketCommodityPrice database models."

    def add_arguments(self, parser):
        parser.add_argument(
            "--file",
            default="data/price_forecasting/datasets/morogoro_rice_beans_updated.csv",
            help=(
                "Path to the training CSV file. Defaults to "
                "data/price_forecasting/datasets/morogoro_rice_beans_updated.csv"
            ),
        )
        parser.add_argument(
            "--user",
            help="Username or email to set as created_by for inserted records.",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=5000,
            help="Batch size for database bulk creation. Defaults to 5000.",
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Delete existing training dataset records (source_key='training_dataset') before importing.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Parse CSV and report statistics without making changes to the database.",
        )

    def handle(self, *args, **options):
        csv_path = Path(options["file"])
        if not csv_path.is_absolute():
            csv_path = Path.cwd() / csv_path

        if not csv_path.exists():
            raise CommandError(f"Training dataset CSV not found at: {csv_path}")

        user = self._get_user(options.get("user"))
        batch_size = options["batch_size"]
        dry_run = options["dry_run"]

        self.stdout.write(f"Reading training data from {csv_path}...")

        if options["clear"] and not dry_run:
            deleted_count, _ = MarketCommodityPrice.objects.filter(source_key="training_dataset").delete()
            self.stdout.write(self.style.WARNING(f"Cleared {deleted_count} existing training price records."))

        with transaction.atomic():
            self._process_import(csv_path, user, batch_size, dry_run)

    def _process_import(self, csv_path, user, batch_size, dry_run):
        region_cache = {}
        ward_cache = {}
        market_cache = {}
        category_cache = {}
        unit_cache = {}
        commodity_cache = {}
        existing_public_ids = set(MarketCommodityPrice.objects.values_list("public_id", flat=True))

        total_rows = 0
        skipped_rows = 0
        params_batch = []
        created_price_count = 0

        insert_sql = """
            INSERT INTO commodities_prices (
                public_id, market_id, commodity_id, unit_id, price_type,
                price, quantity, min_price, max_price, currency,
                source_key, source_name, price_date, created_by_id, created_at, updated_at
            ) VALUES (
                %s, %s, %s, %s, %s::price_type_enum,
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, NOW(), NOW()
            ) ON CONFLICT (market_id, commodity_id, price_date, price_type) WHERE deleted_at IS NULL DO NOTHING;
        """

        with csv_path.open(newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            required_cols = {"date", "region", "kata", "market", "commodity", "unit", "pricetype", "price"}
            missing = required_cols - set(reader.fieldnames or [])
            if missing:
                raise CommandError(f"CSV missing required columns: {', '.join(sorted(missing))}")

            for raw in reader:
                total_rows += 1
                try:
                    price_val = Decimal(raw["price"].strip())
                    price_date_val = date.fromisoformat(raw["date"].strip())
                except (InvalidOperation, ValueError, TypeError, KeyError):
                    skipped_rows += 1
                    continue

                region_name = (raw.get("region") or "").strip()
                ward_name = (raw.get("kata") or "").strip()
                market_name = (raw.get("market") or "").strip()
                category_name = (raw.get("category") or "General").strip().title()
                commodity_name = (raw.get("commodity") or "").strip().title()
                unit_str = (raw.get("unit") or "KG").strip()
                price_type_str = (raw.get("pricetype") or "").strip().lower()
                currency_str = (raw.get("currency") or "TZS").strip().upper()

                lat = self._decimal_or_none(raw.get("latitude"))
                lng = self._decimal_or_none(raw.get("longitude"))

                if not dry_run:
                    # 1. Region
                    if region_name not in region_cache:
                        region_obj, _ = AdmArea.objects.get_or_create(
                            name=region_name,
                            level=AdmArea.Level.REGION,
                            parent=None,
                        )
                        region_cache[region_name] = region_obj
                    region_obj = region_cache[region_name]

                    # 2. Ward
                    ward_key = (ward_name, region_obj.id)
                    if ward_key not in ward_cache:
                        ward_obj, _ = AdmArea.objects.get_or_create(
                            name=ward_name,
                            level=AdmArea.Level.WARD,
                            parent=region_obj,
                        )
                        ward_cache[ward_name, region_obj.id] = ward_obj
                    ward_obj = ward_cache[ward_key]

                    # 3. Market
                    market_key = (market_name, ward_obj.id)
                    if market_key not in market_cache:
                        market_obj, _ = Market.objects.get_or_create(
                            name=market_name,
                            admin_area=ward_obj,
                            deleted_at__isnull=True,
                            defaults={
                                "created_by": user,
                                "status": "active",
                                "latitude": lat,
                                "longitude": lng,
                            },
                        )
                        market_cache[market_key] = market_obj
                    market_obj = market_cache[market_key]

                    # 4. Category
                    if category_name not in category_cache:
                        cat_obj, _ = CommodityCategory.objects.get_or_create(name=category_name)
                        category_cache[category_name] = cat_obj
                    cat_obj = category_cache[category_name]

                    # 5. Unit
                    if unit_str not in unit_cache:
                        unit_obj, _ = CommodityUnit.objects.get_or_create(
                            symbol=unit_str,
                            defaults={"name": unit_str},
                        )
                        unit_cache[unit_str] = unit_obj
                    unit_obj = unit_cache[unit_str]

                    # 6. Commodity
                    if commodity_name not in commodity_cache:
                        com_obj, _ = Commodity.objects.get_or_create(name=commodity_name)
                        CommodityCategoryMap.objects.get_or_create(commodity=com_obj, category=cat_obj)
                        CommodityUnitMap.objects.get_or_create(
                            commodity=com_obj,
                            unit=unit_obj,
                            defaults={"is_primary": True},
                        )
                        commodity_cache[commodity_name] = com_obj
                    com_obj = commodity_cache[commodity_name]

                    pub_id = generate_public_id()
                    while pub_id in existing_public_ids:
                        pub_id = generate_public_id()
                    existing_public_ids.add(pub_id)

                    quantity_val = Decimal("100.00") if "100" in unit_str else Decimal("1.00")
                    price_type_val = price_type_str if price_type_str in ["retail", "wholesale"] else None

                    row_params = (
                        pub_id,
                        market_obj.id,
                        com_obj.id,
                        unit_obj.id,
                        price_type_val,
                        price_val,
                        quantity_val,
                        price_val,
                        price_val,
                        currency_str if currency_str in ["TZS", "USD"] else "TZS",
                        "training_dataset",
                        "Morogoro Training CSV",
                        price_date_val,
                        user.id,
                    )
                    params_batch.append(row_params)

                    if len(params_batch) >= batch_size:
                        with connection.cursor() as cursor:
                            cursor.executemany(insert_sql, params_batch)
                        created_price_count += len(params_batch)
                        self.stdout.write(f"Processed {total_rows} rows... inserted batch up to {created_price_count} prices.")
                        params_batch.clear()

        if not dry_run and params_batch:
            with connection.cursor() as cursor:
                cursor.executemany(insert_sql, params_batch)
            created_price_count += len(params_batch)

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"Dry run complete. Parsed {total_rows} rows ({skipped_rows} skipped). No database changes were made."
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Import complete! Processed {total_rows} rows ({skipped_rows} skipped). "
                    f"Successfully processed {created_price_count} price records into the database."
                )
            )

    def _get_user(self, identifier):
        User = get_user_model()
        queryset = User.objects.all()
        if identifier:
            user = queryset.filter(username=identifier).first() or queryset.filter(email=identifier).first()
            if not user:
                raise CommandError(f"No user found for --user={identifier}")
            return user
        user = queryset.filter(is_superuser=True).first() or queryset.filter(is_staff=True).first() or queryset.first()
        if not user:
            raise CommandError("No user found in database. Create a user first or pass --user.")
        return user

    def _decimal_or_none(self, value):
        if value is None:
            return None
        cleaned = str(value).strip()
        if not cleaned:
            return None
        try:
            return Decimal(cleaned)
        except InvalidOperation:
            return None
