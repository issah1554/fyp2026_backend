import json
from datetime import date
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

from django.conf import settings


DEFAULT_API_BASE_URL = "https://ditapi.databenki.co.tz/api/v1"
UNSPECIFIED_PRICE_TYPE_KEY = "__unspecified__"
UNSPECIFIED_PRICE_TYPE_LABEL = "Not specified"


class LiveMarketPricesUnavailable(Exception):
    pass


class LiveMarketPriceService:
    def __init__(self, base_url=None, timeout=None):
        self.base_url = (
            base_url
            or getattr(settings, "USSD_MARKET_PRICE_API_BASE_URL", DEFAULT_API_BASE_URL)
        ).rstrip("/")
        self.timeout = timeout or getattr(settings, "USSD_MARKET_PRICE_API_TIMEOUT_SECONDS", 10)

    def _request_json(self, path, params=None):
        query = urlencode({key: value for key, value in (params or {}).items() if value not in (None, "")})
        url = f"{self.base_url}/{path.lstrip('/')}"
        if query:
            url = f"{url}?{query}"

        try:
            with urlopen(url, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise LiveMarketPricesUnavailable("Market prices not available right now.") from exc

        if not isinstance(payload, dict) or payload.get("success") is False:
            raise LiveMarketPricesUnavailable("Market prices not available right now.")
        return payload

    def _fetch_paginated(self, path, params=None):
        page = 1
        items = []
        while True:
            payload = self._request_json(path, params={**(params or {}), "page": page, "page_size": 100})
            items.extend(payload.get("data") or [])
            pagination = (payload.get("meta") or {}).get("pagination") or {}
            if not pagination.get("has_next"):
                break
            page += 1
        return items

    def _fetch_market_prices(self, market_id, commodity_id=None):
        return self._fetch_paginated(
            f"markets/{market_id}/prices",
            params={"commodity_id": commodity_id},
        )

    def _normalize_price_type(self, value):
        if value is None:
            return None
        cleaned = str(value).strip()
        return cleaned or None

    def _price_type_key(self, value):
        normalized = self._normalize_price_type(value)
        return normalized or UNSPECIFIED_PRICE_TYPE_KEY

    def _price_type_label(self, value):
        normalized = self._normalize_price_type(value)
        return normalized or UNSPECIFIED_PRICE_TYPE_LABEL

    def _latest_price_rows(self, rows):
        latest_date = None
        latest_rows = []
        for row in rows:
            row_date = row.get("price_date")
            if not row_date:
                continue
            if latest_date is None or row_date > latest_date:
                latest_date = row_date
                latest_rows = [row]
            elif row_date == latest_date:
                latest_rows.append(row)
        latest_rows.sort(key=lambda item: item.get("created_at") or "", reverse=True)
        return latest_rows

    def get_market_options(self):
        markets = self._fetch_paginated("markets")
        return [
            (str(index), {"market_id": item["market_id"], "name": item["name"]})
            for index, item in enumerate(markets, start=1)
            if item.get("market_id") and item.get("name")
        ]

    def get_commodity_options(self, market_id):
        payload = self._request_json(f"markets/{market_id}/latest-prices")
        rows = payload.get("data") or []
        options = []
        seen = set()
        for row in rows:
            commodity = row.get("commodity") or {}
            commodity_id = commodity.get("commodity_id")
            commodity_name = commodity.get("name")
            if not commodity_id or not commodity_name or commodity_id in seen:
                continue
            seen.add(commodity_id)
            options.append({"commodity_id": commodity_id, "name": commodity_name})
        return [(str(index), item) for index, item in enumerate(options, start=1)]

    def get_price_type_options(self, market_id, commodity_id):
        rows = self._latest_price_rows(self._fetch_market_prices(market_id, commodity_id))
        options = []
        seen = set()
        for row in rows:
            key = self._price_type_key(row.get("pricetype") or row.get("price_type"))
            if key in seen:
                continue
            seen.add(key)
            options.append({"value": key, "label": self._price_type_label(row.get("pricetype") or row.get("price_type"))})
        return [(str(index), item) for index, item in enumerate(options, start=1)]

    def get_market_price(self, market_id, commodity_id, selected_price_type):
        rows = self._latest_price_rows(self._fetch_market_prices(market_id, commodity_id))
        for row in rows:
            row_key = self._price_type_key(row.get("pricetype") or row.get("price_type"))
            if row_key != selected_price_type:
                continue

            market = row.get("market") or {}
            commodity = row.get("commodity") or {}
            return {
                "market": market.get("name", "Unknown market"),
                "commodity": commodity.get("name", "Unknown commodity"),
                "pricetype": self._price_type_label(row.get("pricetype") or row.get("price_type")),
                "currency": row.get("currency", "TZS"),
                "price": row.get("price"),
                "min_price": row.get("min_price"),
                "max_price": row.get("max_price"),
                "price_date": row.get("price_date") or date.today().isoformat(),
            }

        raise LiveMarketPricesUnavailable("Selected market price is not available right now.")


def get_market_price_service():
    return LiveMarketPriceService()
