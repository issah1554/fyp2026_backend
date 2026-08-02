from decimal import Decimal, InvalidOperation

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Max
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime

from apps.areas.models import AdmArea
from apps.commodities.models import Commodity
from apps.markets.models import Market, MarketCommodityPrice, RawCommodityPrice

from .clients import MarketSourceError, configured_sources, fetch_json
from .normalizers import NORMALIZERS


def update_source_state(source_key, **fields):
    try:
        from .models import MarketIntegrationSource

        MarketIntegrationSource.all_objects.filter(key=source_key).update(**fields)
    except Exception:
        return


def source_for_key(source_key):
    try:
        from .models import MarketIntegrationSource

        return MarketIntegrationSource.all_objects.filter(key=source_key).first()
    except Exception:
        return None


def available_sources():
    return [
        {
            "key": source.key,
            "name": source.name,
            "source_type": getattr(source, "source_type", "api"),
            "base_url": source.base_url,
            "prices_url": source.url(source.prices_path),
            "health_url": source.url(source.health_path),
            "is_active": getattr(source, "is_active", True),
            "last_checked_at": getattr(source, "last_checked_at", None),
            "last_imported_at": getattr(source, "last_imported_at", None),
            "last_seen_record_at": getattr(source, "last_seen_record_at", None),
        }
        for source in configured_sources().values()
    ]


def source_health():
    results = []
    for source in configured_sources().values():
        try:
            payload = fetch_json(source, source.health_path)
            update_source_state(source.key, last_checked_at=timezone.now())
            results.append({"source": source.key, "name": source.name, "ok": True, "payload": payload})
        except MarketSourceError as exc:
            update_source_state(source.key, last_checked_at=timezone.now())
            results.append({"source": source.key, "name": source.name, "ok": False, "error": str(exc)})
    return results


def normalize_source_prices(source_key, commodity=None, market=None, limit=None):
    sources = configured_sources()
    source = sources[source_key]
    payload = fetch_json(source, source.prices_path)
    normalizer = NORMALIZERS[source_key]
    records = normalizer(payload)
    return filter_records(records, commodity=commodity, market=market, limit=limit)


def aggregate_prices(source_key=None, commodity=None, market=None, limit=None):
    sources = configured_sources()
    selected_keys = [source_key] if source_key else list(sources.keys())
    records = []
    errors = []

    for key in selected_keys:
        if key not in sources:
            errors.append({"source": key, "error": "Unknown market integration source."})
            continue
        try:
            records.extend(normalize_source_prices(key, commodity=commodity, market=market))
        except MarketSourceError as exc:
            errors.append({"source": exc.source_key, "error": str(exc)})

    return {
        "records": records[:limit] if limit else records,
        "errors": errors,
    }


def stored_prices(source_key=None, commodity=None, market=None, limit=None):
    queryset = MarketCommodityPrice.objects.select_related("market", "commodity").filter(currency="TZS")
    if source_key:
        queryset = queryset.filter(source_key=source_key)
    if commodity:
        queryset = queryset.filter(commodity__name__iexact=commodity_name(commodity))
    if market:
        queryset = queryset.filter(market__name__iexact=market)
    if limit:
        queryset = queryset[:limit]
    return queryset


def raw_prices(source_key=None, commodity=None, market=None, limit=None):
    queryset = RawCommodityPrice.objects.select_related("source", "market", "commodity", "unit", "normalized_price")
    if source_key:
        queryset = queryset.filter(source_key=source_key)
    if commodity:
        queryset = queryset.filter(commodity__name__iexact=commodity_name(commodity))
    if market:
        queryset = queryset.filter(market__name__iexact=market)
    if limit:
        queryset = queryset[:limit]
    return queryset


def latest_raw_price(source_key):
    return (
        RawCommodityPrice.objects.filter(source_key=source_key)
        .order_by("-price_date", "-observed_at", "-created_at")
        .first()
    )


def record_fingerprint(record):
    source_key = source_key_for_record(record)
    return (
        source_key,
        source_reference_for_record(record),
        commodity_name(record.get("commodity")),
        record.get("market") or integration_market_name(source_key),
        date_or_none(record.get("price_date"), record.get("timestamp")),
    )


def is_new_record(record, latest_by_source, existing_fingerprints):
    price_date = date_or_none(record.get("price_date"), record.get("timestamp"))
    if price_date is None:
        return False

    source_key = source_key_for_record(record)
    latest = latest_by_source.get(source_key)
    if latest and price_date <= latest.price_date:
        return False

    return record_fingerprint(record) not in existing_fingerprints


def existing_raw_fingerprints(records):
    fingerprints = []
    for record in records:
        price_date = date_or_none(record.get("price_date"), record.get("timestamp"))
        if price_date is None:
            continue
        fingerprints.append(
            {
                "source_key": source_key_for_record(record),
                "source_reference": source_reference_for_record(record),
                "commodity": commodity_name(record.get("commodity")),
                "market": record.get("market") or integration_market_name(source_key_for_record(record)),
                "price_date": price_date,
            }
        )

    existing = set()
    for item in fingerprints:
        queryset = RawCommodityPrice.objects.filter(
            source_key=item["source_key"],
            source_reference=item["source_reference"],
            commodity__name__iexact=item["commodity"],
            market__name__iexact=item["market"],
            price_date=item["price_date"],
        )
        if queryset.exists():
            existing.add(
                (
                    item["source_key"],
                    item["source_reference"],
                    str(item["commodity"] or ""),
                    str(item["market"] or ""),
                    item["price_date"],
                )
            )
    return existing


def check_updates(source_key=None, commodity=None, market=None, limit=None):
    result = aggregate_prices(source_key=source_key, commodity=commodity, market=market, limit=limit)
    sources = sorted({source_key_for_record(record) for record in result["records"]} | ({source_key} if source_key else set()))
    latest_by_source = {key: latest_raw_price(key) for key in sources if key}
    existing = existing_raw_fingerprints(result["records"])

    records_by_source = {}
    new_records_by_source = {}
    for record in result["records"]:
        key = source_key_for_record(record)
        records_by_source.setdefault(key, 0)
        new_records_by_source.setdefault(key, 0)
        records_by_source[key] += 1
        if is_new_record(record, latest_by_source, existing):
            new_records_by_source[key] += 1

    checked_at = timezone.now()
    for key in sources:
        price_date_values = [
            date_or_none(record.get("price_date"), record.get("timestamp"))
            for record in result["records"]
            if source_key_for_record(record) == key
        ]
        price_date_values = [value for value in price_date_values if value is not None]
        update_fields = {"last_checked_at": checked_at}
        if price_date_values:
            update_fields["last_seen_record_at"] = timezone.datetime.combine(
                max(price_date_values),
                timezone.datetime.min.time(),
                tzinfo=timezone.get_current_timezone(),
            )
        update_source_state(key, **update_fields)

    return {
        "sources": [
            {
                "source": key,
                "latest_stored_at": latest_by_source[key].observed_at.isoformat() if latest_by_source.get(key) else None,
                "fetched": records_by_source.get(key, 0),
                "new": new_records_by_source.get(key, 0),
                "has_updates": new_records_by_source.get(key, 0) > 0,
            }
            for key in sources
        ],
        "errors": result["errors"],
    }


def sync_prices(source_key=None, commodity=None, market=None, limit=None, new_only=False):
    import_result = import_raw_prices(source_key=source_key, commodity=commodity, market=market, limit=limit, new_only=new_only)
    standardize_result = standardize_raw_prices(source_key=source_key, commodity=commodity, market=market, limit=limit)
    return {
        "fetched": import_result["fetched"],
        "selected": import_result["selected"],
        "created": standardize_result["created"],
        "updated": standardize_result["updated"],
        "errors": import_result["errors"],
    }


def import_raw_prices(source_key=None, commodity=None, market=None, limit=None, new_only=False):
    result = aggregate_prices(source_key=source_key, commodity=commodity, market=market, limit=limit)
    latest_by_source = {
        key: latest_raw_price(key)
        for key in {source_key_for_record(record) for record in result["records"]}
    }
    existing = existing_raw_fingerprints(result["records"]) if new_only else set()
    records = [
        record
        for record in result["records"]
        if not new_only or is_new_record(record, latest_by_source, existing)
    ]
    created = 0
    updated = 0

    with transaction.atomic():
        for record in records:
            raw_price, was_created = upsert_raw_price(record)
            if raw_price:
                if was_created:
                    created += 1
                else:
                    updated += 1

    imported_at = timezone.now()
    for key in {source_key_for_record(record) for record in records}:
        latest_observed = RawCommodityPrice.objects.filter(source_key=key).aggregate(value=Max("observed_at"))["value"]
        latest_price_date = RawCommodityPrice.objects.filter(source_key=key).aggregate(value=Max("price_date"))["value"]
        update_source_state(
            key,
            last_imported_at=imported_at,
            last_seen_record_at=latest_observed
            or (
                timezone.datetime.combine(
                    latest_price_date,
                    timezone.datetime.min.time(),
                    tzinfo=timezone.get_current_timezone(),
                )
                if latest_price_date
                else None
            ),
        )

    return {
        "fetched": len(result["records"]),
        "selected": len(records),
        "created": created,
        "updated": updated,
        "errors": result["errors"],
    }


def standardize_raw_prices(source_key=None, commodity=None, market=None, limit=None):
    queryset = raw_prices(source_key=source_key, commodity=commodity, market=market).filter(normalized_price__isnull=True)
    if limit:
        queryset = queryset[:limit]

    created = 0
    updated = 0
    with transaction.atomic():
        for group in raw_price_groups(queryset):
            _, was_created = standardize_raw_price_group(group)
            if was_created:
                created += 1
            else:
                updated += 1
    return {"created": created, "updated": updated, "errors": []}


def raw_price_groups(queryset):
    groups = {}
    for raw_price in queryset:
        key = (
            raw_price.market_id,
            raw_price.commodity_id,
            raw_price.price_date,
            raw_price.price_type,
            raw_price.unit_id,
            raw_price.currency,
        )
        groups[key] = raw_price
    return groups.values()


def grouped_raw_prices(raw_price):
    return RawCommodityPrice.objects.filter(
        market=raw_price.market,
        commodity=raw_price.commodity,
        price_date=raw_price.price_date,
        price_type=raw_price.price_type,
        unit=raw_price.unit,
        currency=raw_price.currency,
        deleted_at__isnull=True,
    )


def average_decimal(values):
    values = [value for value in values if value is not None]
    if not values:
        return Decimal("0.00")
    return (sum(values) / Decimal(len(values))).quantize(Decimal("0.01"))


def source_summary(raw_rows):
    source_keys = sorted({row.source_key for row in raw_rows if row.source_key})
    source_names = sorted({row.source_name for row in raw_rows if row.source_name})
    if len(source_keys) == 1:
        return source_keys[0], source_names[0] if source_names else source_keys[0]
    return "aggregated", f"Aggregated ({len(source_keys)} sources)"


def standardize_raw_price_group(raw_price):
    user = integration_user()
    raw_rows = list(grouped_raw_prices(raw_price))
    source_key, source_name = source_summary(raw_rows)
    prices = [row.price for row in raw_rows]
    quantities = [row.quantity for row in raw_rows]

    market_price, was_created = MarketCommodityPrice.all_objects.update_or_create(
        market=raw_price.market,
        commodity=raw_price.commodity,
        price_date=raw_price.price_date,
        price_type=raw_price.price_type,
        deleted_at__isnull=True,
        defaults={
            "price": average_decimal(prices),
            "quantity": average_decimal(quantities),
            "unit": raw_price.unit,
            "min_price": min(prices) if prices else None,
            "max_price": max(prices) if prices else None,
            "currency": raw_price.currency,
            "source_key": source_key,
            "source_name": source_name,
            "created_by": user,
            "updated_by": user,
        },
    )

    RawCommodityPrice.all_objects.filter(pk__in=[row.pk for row in raw_rows]).update(
        normalized_price=market_price,
        updated_by_id=user.pk if user else None,
        updated_at=timezone.now(),
    )
    return market_price, was_created


def upsert_raw_price(record):
    observed_at = datetime_or_none(record.get("timestamp"))
    price_date = date_or_none(record.get("price_date"), record.get("timestamp"))
    if observed_at is None or price_date is None:
        return None, False

    source_key = source_key_for_record(record)
    source = source_for_key(source_key)
    market = get_or_create_market(record, source_key)
    commodity = get_or_create_commodity(record["commodity"])
    user = integration_user()
    unit = get_primary_or_default_unit(commodity)
    price_tzs = decimal_or_none(record.get("price_tzs")) or Decimal("0")
    source_name = record.get("source", "")
    price_type = MarketCommodityPrice.PriceType.WHOLESALE

    raw_price, was_created = RawCommodityPrice.all_objects.update_or_create(
        market=market,
        commodity=commodity,
        price_date=price_date,
        price_type=price_type,
        source_key=source_key,
        source_reference=source_reference_for_record(record),
        deleted_at__isnull=True,
        defaults={
            "price": price_tzs,
            "quantity": Decimal("1.00"),
            "unit": unit,
            "currency": RawCommodityPrice.Currency.TZS,
            "source": source,
            "source_name": source_name,
            "observed_at": observed_at,
            "raw_payload": record.get("raw") or record,
            "created_by": user,
            "updated_by": user,
        },
    )
    return raw_price, was_created


def integration_user():
    User = get_user_model()
    user = User.objects.filter(email="system.market_officer@user.com").first()
    if user:
        return user
    user = User.objects.filter(is_superuser=True).first()
    if user:
        return user
    return User.objects.filter(is_staff=True).first() or User.objects.first()


def get_or_create_commodity(symbol):
    name = commodity_name(symbol)
    commodity = Commodity.objects.filter(name__iexact=name).first()
    if not commodity:
        commodity = Commodity.objects.create(name=name)
    from apps.commodities.models import CommodityUnit, CommodityUnitMap
    unit, _ = CommodityUnit.objects.get_or_create(
        symbol="kg",
        defaults={"name": "Kilogram"}
    )
    CommodityUnitMap.objects.get_or_create(
        commodity=commodity,
        unit=unit,
        defaults={"is_primary": True}
    )
    return commodity


def get_primary_or_default_unit(commodity):
    from apps.commodities.models import CommodityUnit, CommodityUnitMap

    primary_map = CommodityUnitMap.objects.filter(commodity=commodity, is_primary=True).first()
    if primary_map:
        return primary_map.unit
    unit, _ = CommodityUnit.objects.get_or_create(
        symbol="kg",
        defaults={"name": "Kilogram"},
    )
    CommodityUnitMap.objects.get_or_create(
        commodity=commodity,
        unit=unit,
        defaults={"is_primary": True},
    )
    return unit


def get_or_create_market(record, source_key):
    market_name = record.get("market") or integration_market_name(source_key)
    market = Market.objects.filter(name__iexact=market_name).first()
    if market:
        return market

    admin_area = default_admin_area()
    user = integration_user()
    return Market.objects.create(
        name=market_name,
        code=integration_market_code(source_key, market_name),
        admin_area=admin_area,
        description="Created from market integration feed.",
        created_by=user,
    )


def default_admin_area():
    return (
        AdmArea.objects.filter(name__iexact="Dar-es-salaam", level=AdmArea.Level.REGION).first()
        or AdmArea.objects.filter(name__iexact="Dar es Salaam", level=AdmArea.Level.REGION).first()
        or AdmArea.objects.filter(level=AdmArea.Level.REGION).first()
        or AdmArea.objects.first()
    )


def commodity_name(symbol):
    mapping = {
        "MAIZE": "Maize",
        "RICE": "Rice",
        "WHEAT": "Wheat Grain",
        "COCOA": "Cocoa",
        "COFFEE": "Coffee",
    }
    return mapping.get(str(symbol).upper(), str(symbol).title())


def check_viwanda_updates():
    from apps.market_integrations.scrapper.pdfs_collector import collect_documents, save_documents
    from apps.market_integrations.scrapper.downloader import download_documents
    from apps.market_integrations.scrapper.extract_prices import extract_all_prices, write_json

    # 1. Collect only first 2 pages of viwanda website for fast updates
    documents = collect_documents(max_pages=2)
    save_documents(documents)

    # 2. Download any new PDFs
    downloaded = download_documents()

    # 3. Extract prices from downloaded PDFs to update the local prices.json
    records = extract_all_prices()
    write_json(records)

    # 4. Sync the prices into Django DB
    sync_result = sync_prices(source_key="viwanda")
    return {
        "downloaded_count": len(downloaded),
        "total_extracted": len(records),
        "sync_result": sync_result
    }


def integration_market_name(source_key):
    mapping = {
        "platform_a": "Platform A Integration Market",
        "platform_b": "Platform B Integration Market",
        "internal": "Internal System Collected Market",
        "viwanda": "Ministry of Industry and Trade Integration Market",
    }
    return mapping.get(source_key, f"{source_key.replace('_', ' ').title()} Integration Market")


def integration_market_code(source_key, market_name=None):
    if market_name:
        slug = "".join(char for char in market_name.upper() if char.isalnum())[:40]
        return f"INT-{slug}"
    return f"INT-{source_key.upper()}"


def filter_records(records, commodity=None, market=None, limit=None):
    filtered = records
    if commodity:
        filtered = [record for record in filtered if record["commodity"].lower() == commodity.lower()]
    if market:
        filtered = [
            record
            for record in filtered
            if record.get("market") and record["market"].lower() == market.lower()
        ]
    return filtered[:limit] if limit else filtered


def source_key_for_record(record):
    source_name = record.get("source", "").lower()
    if source_name == "platform a":
        return "platform_a"
    if source_name == "platform b":
        return "platform_b"
    if source_name in ("internal system", "internal", "market officers", "market officer"):
        return "internal"
    if source_name in ("viwanda", "scrapper", "ministry of industry and trade"):
        return "viwanda"
    return source_name.replace(" ", "_")


def source_reference_for_record(record):
    raw = record.get("raw") or {}
    for key in ("source_reference", "document", "document_name", "filename", "file", "url"):
        value = raw.get(key) or record.get(key)
        if value:
            return str(value)[:255]
    return ""


def decimal_or_none(value):
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def datetime_or_none(value):
    if not value:
        return None
    parsed = parse_datetime(value)
    return parsed


def date_or_none(value, fallback_timestamp=None):
    if value:
        parsed = parse_date(str(value)[:10])
        if parsed:
            return parsed
    parsed_timestamp = datetime_or_none(fallback_timestamp)
    return parsed_timestamp.date() if parsed_timestamp else None


def model_defaults(record):
    return {
        "source_name": record.get("source", ""),
        "commodity": record.get("commodity", ""),
        "market": record.get("market") or "",
        "price_tzs": decimal_or_none(record.get("price_tzs")),
        "price_usd": decimal_or_none(record.get("price_usd")),
        "volume": decimal_or_none(record.get("volume")),
        "confidence": decimal_or_none(record.get("confidence")),
        "delay_minutes": record.get("delay_minutes"),
        "price_date": date_or_none(record.get("price_date"), record.get("timestamp")),
        "observed_at": datetime_or_none(record.get("timestamp")),
        "raw_payload": record.get("raw") or {},
    }
