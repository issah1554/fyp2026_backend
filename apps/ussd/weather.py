from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from urllib.parse import urlencode
from urllib.request import urlopen

from django.utils import timezone

from .forecasting import get_season_name


OPEN_METEO_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"


class WeatherForecastUnavailable(Exception):
    pass


@dataclass(frozen=True)
class WeatherRegion:
    name: str
    latitude: float
    longitude: float


WEATHER_REGIONS = (
    WeatherRegion("Dar es Salaam", -6.7924, 39.2083),
    WeatherRegion("Morogoro", -6.8278, 37.6591),
    WeatherRegion("Dodoma", -6.1630, 35.7516),
    WeatherRegion("Arusha", -3.3869, 36.6830),
    WeatherRegion("Mwanza", -2.5164, 32.9175),
)


def get_weather_region_options() -> list[tuple[str, WeatherRegion]]:
    return [(str(index), region) for index, region in enumerate(WEATHER_REGIONS, start=1)]


def _condition_from_code(code: int) -> str:
    if code == 0:
        return "Sunny"
    if code in (1, 2):
        return "Partly cloudy"
    if code == 3:
        return "Cloudy"
    if code in (45, 48):
        return "Foggy"
    if code in (51, 53, 55, 56, 57):
        return "Drizzle"
    if code in (61, 63, 65, 66, 67):
        return "Rainy"
    if code in (71, 73, 75, 77):
        return "Very cold"
    if code in (80, 81, 82):
        return "Showers"
    if code in (85, 86):
        return "Very cold"
    if code in (95, 96, 99):
        return "Thunderstorms"
    return "Mixed weather"


def _rain_guidance(probability, precipitation) -> str:
    rain_probability = int(probability or 0)
    rain_amount = float(precipitation or 0)
    if rain_probability >= 60 or rain_amount >= 5:
        return "rain likely"
    if rain_probability >= 30 or rain_amount > 0:
        return "possible rain"
    return "low rain"


def _weekday_label(value: str) -> str:
    return date.fromisoformat(value).strftime("%A")


class OpenMeteoWeatherService:
    def fetch_weekly_forecast(self, region: WeatherRegion) -> dict:
        params = urlencode(
            {
                "latitude": region.latitude,
                "longitude": region.longitude,
                "daily": ",".join(
                    [
                        "weather_code",
                        "temperature_2m_max",
                        "temperature_2m_min",
                        "precipitation_probability_max",
                        "precipitation_sum",
                    ]
                ),
                "timezone": "Africa/Dar_es_Salaam",
                "forecast_days": 7,
            }
        )
        try:
            with urlopen(f"{OPEN_METEO_FORECAST_URL}?{params}", timeout=10) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            raise WeatherForecastUnavailable("Weather forecast not available right now.") from exc

        daily = payload.get("daily") or {}
        dates = daily.get("time") or []
        codes = daily.get("weather_code") or []
        max_temperatures = daily.get("temperature_2m_max") or []
        min_temperatures = daily.get("temperature_2m_min") or []
        rain_probabilities = daily.get("precipitation_probability_max") or []
        precipitation = daily.get("precipitation_sum") or []
        if not dates or not codes:
            raise WeatherForecastUnavailable("Weather forecast not available right now.")

        days = []
        for index, day in enumerate(dates[:7]):
            condition = _condition_from_code(int(codes[index]))
            guidance = _rain_guidance(
                rain_probabilities[index] if index < len(rain_probabilities) else 0,
                precipitation[index] if index < len(precipitation) else 0,
            )
            min_temp = round(float(min_temperatures[index])) if index < len(min_temperatures) else None
            max_temp = round(float(max_temperatures[index])) if index < len(max_temperatures) else None
            temperature = (
                f"{min_temp}-{max_temp}C"
                if min_temp is not None and max_temp is not None
                else "temp unavailable"
            )
            days.append(
                {
                    "date": day,
                    "weekday": _weekday_label(day),
                    "condition": condition,
                    "guidance": guidance,
                    "temperature": temperature,
                }
            )

        today = timezone.localdate()
        return {
            "region": region.name,
            "season": get_season_name(__import__("pandas").Timestamp(today)),
            "days": days,
        }


def get_weather_service() -> OpenMeteoWeatherService:
    return OpenMeteoWeatherService()
