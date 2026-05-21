from __future__ import annotations

import logging
from typing import Literal

import httpx
from langchain_core.tools import tool
from pydantic import BaseModel, Field

GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
HTTP_TIMEOUT = 5.0

# WMO weather interpretation codes — https://open-meteo.com/en/docs
_WMO = {
    0: "clear sky",
    1: "mainly clear", 2: "partly cloudy", 3: "overcast",
    45: "fog", 48: "depositing rime fog",
    51: "light drizzle", 53: "drizzle", 55: "heavy drizzle",
    56: "light freezing drizzle", 57: "freezing drizzle",
    61: "light rain", 63: "rain", 65: "heavy rain",
    66: "light freezing rain", 67: "freezing rain",
    71: "light snow", 73: "snow", 75: "heavy snow", 77: "snow grains",
    80: "light rain showers", 81: "rain showers", 82: "violent rain showers",
    85: "light snow showers", 86: "snow showers",
    95: "thunderstorm", 96: "thunderstorm with light hail", 99: "thunderstorm with hail",
}


class WeatherArgs(BaseModel):
    location: str = Field(description="City name to look up weather for, e.g. 'Lucknow' or 'Delhi'.")
    when: Literal["now", "today", "tomorrow"] = Field(
        default="now",
        description="When to report weather for. 'now' = current conditions, 'today'/'tomorrow' = daily forecast.",
    )


def _describe_code(code: int | None) -> str:
    if code is None:
        return "unknown conditions"
    return _WMO.get(int(code), f"weather code {code}")


@tool("get_weather", args_schema=WeatherArgs)
async def get_weather(location: str, when: str = "now") -> str:
    """Look up current weather or a short forecast for a city.

    Use this whenever the user asks about weather, temperature, rain, humidity,
    wind, or whether a trip / outdoor plan is okay condition-wise. If the user
    doesn't name a city, fall back to the location in their profile.

    Returns a short human-readable summary; the model should paraphrase it into
    the final reply.
    """
    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            geo = await client.get(GEOCODE_URL, params={"name": location, "count": 1})
            geo.raise_for_status()
            geo_data = geo.json()
            results = geo_data.get("results") or []
            if not results:
                return f"Couldn't find a place called '{location}'. Ask the user to clarify the city."

            place = results[0]
            lat, lon = place["latitude"], place["longitude"]
            resolved = ", ".join(p for p in [place.get("name"), place.get("admin1"), place.get("country")] if p)

            forecast = await client.get(
                FORECAST_URL,
                params={
                    "latitude": lat,
                    "longitude": lon,
                    "current": "temperature_2m,apparent_temperature,relative_humidity_2m,precipitation,weather_code,wind_speed_10m",
                    "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max",
                    "timezone": "auto",
                    "forecast_days": 2,
                },
            )
            forecast.raise_for_status()
            data = forecast.json()
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        logging.exception("weather lookup failed for %s", location)
        return f"Couldn't fetch weather for {location} right now ({exc.__class__.__name__})."

    if when == "now":
        cur = data.get("current") or {}
        return (
            f"{resolved} — now: {cur.get('temperature_2m')}°C "
            f"(feels like {cur.get('apparent_temperature')}°C), "
            f"{_describe_code(cur.get('weather_code'))}, "
            f"humidity {cur.get('relative_humidity_2m')}%, "
            f"wind {cur.get('wind_speed_10m')} km/h, "
            f"precipitation {cur.get('precipitation')} mm."
        )

    daily = data.get("daily") or {}
    idx = 0 if when == "today" else 1
    try:
        return (
            f"{resolved} — {when}: "
            f"high {daily['temperature_2m_max'][idx]}°C / low {daily['temperature_2m_min'][idx]}°C, "
            f"{_describe_code(daily['weather_code'][idx])}, "
            f"rain chance {daily['precipitation_probability_max'][idx]}%."
        )
    except (IndexError, KeyError):
        return f"Couldn't read the {when} forecast for {resolved}."
