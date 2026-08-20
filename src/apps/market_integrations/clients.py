import json
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.conf import settings
from django.db import OperationalError, ProgrammingError


DEFAULT_TIMEOUT_SECONDS = 8


@dataclass(frozen=True)
class MarketDataSource:
    key: str
    name: str
    base_url: str
    source_type: str = "api"
    prices_path: str = "/api/prices"
    health_path: str = "/api/health"
    is_active: bool = True

    def url(self, path):
        if not self.base_url:
            return ""
        return f"{self.base_url.rstrip('/')}/{path.lstrip('/')}"


class MarketSourceError(Exception):
    def __init__(self, source_key, message):
        self.source_key = source_key
        super().__init__(message)


def configured_sources():
    try:
        from .models import MarketIntegrationSource

        sources = MarketIntegrationSource.objects.filter(is_active=True)
        if sources.exists():
            return {source.key: source for source in sources}
    except (OperationalError, ProgrammingError):
        pass

    configured = getattr(settings, "MARKET_INTEGRATION_SOURCES", None)
    defaults = configured or {
        "platform_a": {
            "name": "Platform A",
            "base_url": "http://localhost:3001",
        },
        "platform_b": {
            "name": "Platform B",
            "base_url": "http://localhost:3002",
        },
        "internal": {
            "name": "Internal System",
            "source_type": "internal",
            "base_url": "",
        },
        "viwanda": {
            "name": "Ministry of Industry and Trade",
            "source_type": "scraper",
            "base_url": "https://www.viwanda.go.tz",
            "prices_path": "/documents/product-prices-domestic",
            "health_path": "/documents/product-prices-domestic",
        },
    }
    return {
        key: MarketDataSource(
            key=key,
            name=value["name"],
            source_type=value.get("source_type", "api"),
            base_url=value.get("base_url", ""),
            prices_path=value.get("prices_path", "/api/prices"),
            health_path=value.get("health_path", "/api/health"),
            is_active=value.get("is_active", True),
        )
        for key, value in defaults.items()
    }


def fetch_json(source, path, params=None):
    if source.key == "internal":
        try:
            from apps.markets.models import MarketCommodityPrice
            queryset = MarketCommodityPrice.objects.select_related("market", "commodity").filter(source_key="internal")
            results = []
            for item in queryset:
                results.append({
                    "name": item.commodity.name,
                    "latest_price_tzs": float(item.price),
                    "latest_price_usd": float(item.price_usd) if item.price_usd else None,
                    "volume": float(item.quantity) if item.quantity else None,
                    "confidence": 1.0,
                    "delay_minutes": 0,
                    "time": item.price_date.isoformat(),
                })
            return {"provider": "Internal System", "results": results}
        except Exception as exc:
            raise MarketSourceError(source.key, f"Failed to load internal price data: {exc}") from exc

    if source.key == "viwanda":
        from pathlib import Path

        file_path = Path(settings.BASE_DIR) / "src" / "apps" / "market_integrations" / "scrapper" / "data" / "prices.json"
        try:
            with file_path.open("r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as exc:
            raise MarketSourceError(source.key, f"Failed to read local scraper cache at {file_path}: {exc}") from exc

    url = source.url(path)
    if params:
        url = f"{url}?{urlencode(params)}"

    request = Request(url, headers={"Accept": "application/json"})
    timeout = getattr(settings, "MARKET_INTEGRATION_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_SECONDS)
    try:
        with urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise MarketSourceError(source.key, f"{source.name} returned HTTP {exc.code}.") from exc
    except URLError as exc:
        raise MarketSourceError(source.key, f"{source.name} is unreachable: {exc.reason}.") from exc
    except TimeoutError as exc:
        raise MarketSourceError(source.key, f"{source.name} timed out.") from exc
    except json.JSONDecodeError as exc:
        raise MarketSourceError(source.key, f"{source.name} returned invalid JSON.") from exc
