"""AQI lookup (Open-Meteo, free, no API key) and US AQI categories."""
import json
import urllib.parse
import urllib.request

URL = "https://air-quality-api.open-meteo.com/v1/air-quality"

# (upper bound, name) on the US AQI scale
BANDS = [
    (50, "Good"),
    (100, "Moderate"),
    (150, "Unhealthy for Sensitive Groups"),
    (200, "Unhealthy"),
    (300, "Very Unhealthy"),
    (10**6, "Hazardous"),
]


def category(aqi: int) -> str:
    for upper, name in BANDS:
        if aqi <= upper:
            return name
    return BANDS[-1][1]


def fetch_aqi(lat: float, lon: float, timeout: int = 8) -> dict:
    query = urllib.parse.urlencode(
        {"latitude": lat, "longitude": lon, "current": "us_aqi,pm2_5"}
    )
    with urllib.request.urlopen(f"{URL}?{query}", timeout=timeout) as resp:
        current = json.load(resp)["current"]
    return {"aqi": int(current["us_aqi"]), "pm25": current.get("pm2_5")}
