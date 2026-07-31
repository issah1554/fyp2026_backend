import json
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.conf import settings


DEFAULT_TIMEOUT_SECONDS = 8


@dataclass(frozen=True)
class MarketDataSource:
    key: str
    name: str
    base_url: str
    prices_path: str = "/api/prices"
    health_path: str = "/api/health"

    def url(self, path):
        return f"{self.base_url.rstrip('/')}/{path.lstrip('/')}"


class MarketSourceError(Exception):
    def __init__(self, source_key, message):
        self.source_key = source_key
        super().__init__(message)


def configured_sources():
    defaults = {
        "platform_a": {
            "name": "Platform A",
            "base_url": "http://localhost:3001",
        },
        "platform_b": {
            "name": "Platform B",
            "base_url": "http://localhost:3002",
        },
        "platform_c": {
            "name": "Platform C",
            "base_url": "http://localhost:3003",
        },
    }
    configured = getattr(settings, "MARKET_INTEGRATION_SOURCES", defaults)
    return {
        key: MarketDataSource(
            key=key,
            name=value["name"],
            base_url=value["base_url"],
            prices_path=value.get("prices_path", "/api/prices"),
            health_path=value.get("health_path", "/api/health"),
        )
        for key, value in configured.items()
    }


def fetch_json(source, path, params=None):
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
