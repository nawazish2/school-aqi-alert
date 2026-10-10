"""Pure decision + validation logic (no AWS), shared by Lambda and the local server."""
import re
import unicodedata

import advice
import aqi as aqi_mod

PHONE_RE = re.compile(r"^\+[1-9]\d{7,14}$")


def evaluate(school: dict, reading: dict, threshold: int, today: str, forced: bool = False) -> dict:
    value = reading["aqi"]
    cat = aqi_mod.category(value)
    message = advice.build_message(school["name"], value, cat, school.get("lang", "en"))
    should_alert = value >= threshold and (forced or school.get("last_alert_date") != today)
    return {"aqi": value, "category": cat, "message": message, "should_alert": should_alert}


def forced_reading(value: int) -> dict:
    return {"aqi": value, "current": value, "peak": value, "hourly": []}


def slugify(name: str) -> str:
    text = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40] or "school"


def validate_school(body: dict) -> dict:
    """Return a clean school record or raise ValueError with a user-facing message."""
    name = str(body.get("name", "")).strip()
    if not 2 <= len(name) <= 80:
        raise ValueError("name must be 2-80 characters")
    try:
        lat, lon = float(body["lat"]), float(body["lon"])
    except (KeyError, TypeError, ValueError):
        raise ValueError("lat and lon are required numbers")
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError("lat/lon out of range")
    phone = str(body.get("phone", "")).strip().replace(" ", "")
    if phone and not PHONE_RE.match(phone):
        raise ValueError("phone must look like +919876543210")
    lang = body.get("lang", "en")
    if lang not in advice.LANGS:
        raise ValueError("lang must be en, hi or both")
    return {
        "school_id": slugify(name),
        "name": name,
        "lat": round(lat, 5),
        "lon": round(lon, 5),
        "phone": phone,
        "lang": lang,
    }
