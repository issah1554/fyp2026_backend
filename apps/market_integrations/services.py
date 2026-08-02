from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.contrib.auth import get_user_model
from django.utils.dateparse import parse_datetime

from apps.areas.models import AdmArea
from apps.commodities.models import Commodity
from apps.markets.models import Market, MarketCommodityPrice, RawCommodityPrice

from .clients import MarketSourceError, configured_sources, fetch_json
from .normalizers import NORMALIZERS


def available_sources():
    return [
        {
            "key": source.key,
            "name": source.name,
            "base_url": source.base_url,
            "prices_url": source.url(source.prices_path),
            "health_url": source.url(source.health_path),
        }
        for source in configured_sources().values()
    ]


def source_health():
    results = []
    for source in configured_sources().values():
        try:
            payload = fetch_json(source, source.health_path)
            results.append({"source": source.key, "name": source.name, "ok": True, "payload": payload})
        except MarketSourceError as exc:
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


def sync_prices(source_key=None, commodity=None, market=None, limit=None):
    result = aggregate_prices(source_key=source_key, commodity=commodity, market=market, limit=limit)
    created = 0
    updated = 0

    with transaction.atomic():
        for record in result["records"]:
            market_price, was_created = upsert_market_price(record)
            if market_price:
                if was_created:
                    created += 1
                else:
                    updated += 1

    return {
        "created": created,
        "updated": updated,
        "errors": result["errors"],
    }


def upsert_market_price(record):
    observed_at = datetime_or_none(record.get("timestamp"))
    if observed_at is None:
        return None, False

    source_key = source_key_for_record(record)
    market = get_or_create_market(record, source_key)
    commodity = get_or_create_commodity(record["commodity"])
    user = integration_user()
    unit = get_primary_or_default_unit(commodity)
    price_date = observed_at.date()
    price_tzs = decimal_or_none(record.get("price_tzs")) or Decimal("0")
    source_name = record.get("source", "")
    price_type = MarketCommodityPrice.PriceType.WHOLESALE

    market_price, was_created = MarketCommodityPrice.all_objects.update_or_create(
        market=market,
        commodity=commodity,
        price_date=price_date,
        price_type=price_type,
        deleted_at__isnull=True,
        defaults={
            "price": price_tzs,
            "quantity": Decimal("1.00"),
            "unit": unit,
            "currency": MarketCommodityPrice.Currency.TZS,
            "source_key": source_key,
            "source_name": source_name,
            "created_by": user,
            "updated_by": user,
        },
    )
    RawCommodityPrice.all_objects.update_or_create(
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
            "source_name": source_name,
            "observed_at": observed_at,
            "raw_payload": record.get("raw") or record,
            "normalized_price": market_price,
            "created_by": user,
            "updated_by": user,
        },
    )
    return market_price, was_created


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
    if source_name in ("internal system", "internal", "platform c", "market officers", "market officer"):
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
        "observed_at": datetime_or_none(record.get("timestamp")),
        "raw_payload": record.get("raw") or {},
    }
