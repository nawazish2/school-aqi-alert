"""AQI lookup (Open-Meteo, free, no API key): current reading + school-hours forecast."""
import json
import urllib.parse
import urllib.request

URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
SCHOOL_HOURS = range(7, 16)  # 07:00-15:59 local time

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


def parse_response(data: dict) -> dict:
    """Current AQI, today's school-hours peak and the next 24 hourly values.

    The alert is based on max(current, school-hours peak), so principals are
    warned about the day ahead, not just the 6:30 AM reading.
    """
    current = int(data["current"]["us_aqi"])
    now = data["current"]["time"]  # e.g. 2026-10-10T06:30
    today, now_hour = now[:10], int(now[11:13])
    times = data["hourly"]["time"]
    values = data["hourly"]["us_aqi"]

    peak = current
    upcoming = []
    for t, v in zip(times, values):
        if v is None:
            continue
        if t[:10] == today and int(t[11:13]) in SCHOOL_HOURS:
            peak = max(peak, int(v))
        if t[:10] > today or (t[:10] == today and int(t[11:13]) >= now_hour):
            upcoming.append(int(v))
    return {
        "aqi": max(current, peak),
        "current": current,
        "peak": peak,
        "hourly": upcoming[:24],
        "pm25": data["current"].get("pm2_5"),
    }


def fetch_aqi(lat: float, lon: float, timeout: int = 8) -> dict:
    query = urllib.parse.urlencode(
        {
            "latitude": lat,
            "longitude": lon,
            "current": "us_aqi,pm2_5",
            "hourly": "us_aqi",
            "forecast_days": 2,
            "timezone": "Asia/Kolkata",
        }
    )
    with urllib.request.urlopen(f"{URL}?{query}", timeout=timeout) as resp:
        return parse_response(json.load(resp))
