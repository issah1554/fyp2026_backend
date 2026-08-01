from datetime import UTC, datetime


def as_float(value):
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_timestamp(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
    try:
        normalized = value.replace("Z", "+00:00")
        return datetime.fromisoformat(normalized).astimezone(UTC).isoformat().replace("+00:00", "Z")
    except ValueError:
        return value


def normalized_record(
    *,
    source,
    commodity,
    price_tzs,
    price_usd,
    timestamp,
    market=None,
    volume=None,
    confidence=None,
    delay_minutes=None,
    raw=None,
):
    return {
        "source": source,
        "commodity": str(commodity).upper() if commodity else "",
        "price_tzs": as_float(price_tzs),
        "price_usd": as_float(price_usd),
        "market": market,
        "volume": as_float(volume),
        "confidence": as_float(confidence),
        "delay_minutes": delay_minutes,
        "timestamp": parse_timestamp(timestamp),
        "raw": raw,
    }


def normalize_platform_a(payload):
    source = payload.get("platform", "Platform A")
    return [
        normalized_record(
            source=source,
            commodity=item.get("symbol"),
            price_tzs=item.get("price_tzs"),
            price_usd=item.get("price_usd"),
            volume=item.get("volume"),
            timestamp=item.get("timestamp"),
            raw=item,
        )
        for item in payload.get("items", [])
    ]


def normalize_platform_b(payload):
    source = payload.get("source_name", "Platform B")
    return [
        normalized_record(
            source=source,
            commodity=item.get("commodity"),
            price_tzs=item.get("amount_tzs"),
            price_usd=item.get("amount_usd"),
            market=item.get("market"),
            timestamp=item.get("updated_at"),
            raw=item,
        )
        for item in payload.get("data", [])
    ]


def normalize_market_officers(payload):
    source = payload.get("provider", "Market Officers")
    return [
        normalized_record(
            source=source,
            commodity=item.get("name"),
            price_tzs=item.get("latest_price_tzs"),
            price_usd=item.get("latest_price_usd"),
            volume=item.get("volume"),
            confidence=item.get("confidence"),
            delay_minutes=item.get("delay_minutes"),
            timestamp=item.get("time"),
            raw=item,
        )
        for item in payload.get("results", [])
    ]


def normalize_viwanda(payload):
    if not isinstance(payload, list):
        payload = []
    records = []
    for item in payload:
        min_p = item.get("min_price")
        max_p = item.get("max_price")
        if min_p is not None and max_p is not None:
            price_tzs = (min_p + max_p) / 2
        elif min_p is not None:
            price_tzs = min_p
        elif max_p is not None:
            price_tzs = max_p
        else:
            price_tzs = None

        raw_commodity = item.get("commodity") or ""
        commodity = raw_commodity.split("(")[0].strip()

        records.append(
            normalized_record(
                source="Ministry of Industry and Trade",
                commodity=commodity,
                price_tzs=price_tzs,
                price_usd=None,
                market=item.get("market"),
                timestamp=item.get("date"),
                raw=item,
            )
        )
    return records


NORMALIZERS = {
    "platform_a": normalize_platform_a,
    "platform_b": normalize_platform_b,
    "market_officers": normalize_market_officers,
    "viwanda": normalize_viwanda,
}
