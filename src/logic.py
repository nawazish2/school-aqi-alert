"""Pure decision + validation logic (no AWS), shared by Lambda and the local server."""
import re
import secrets
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
    raw = body.get("contacts") or []
    if isinstance(raw, str):
        raw = raw.split(",")
    contacts = [str(c).strip().replace(" ", "") for c in raw if str(c).strip()]
    if len(contacts) > 5 or any(not PHONE_RE.match(c) for c in contacts):
        raise ValueError("contacts must be up to 5 phone numbers like +919876543210")
    lang = body.get("lang", "en")
    if lang not in advice.LANGS:
        raise ValueError("lang must be en, hi or both")
    return {
        "school_id": slugify(name),
        "name": name,
        "lat": round(lat, 5),
        "lon": round(lon, 5),
        "phone": phone,
        "contacts": contacts,
        "lang": lang,
    }


# ---- accountability loop: alert -> confirm link -> escalate -------------------

def new_token(school_id: str) -> str:
    return f"{school_id}.{secrets.token_urlsafe(8)}"


def school_id_from_token(token: str) -> str:
    return token.rsplit(".", 1)[0] if "." in token else ""


def with_confirm_link(message: str, base_url: str, token: str) -> str:
    if not base_url:
        return message
    return f"{message}\nConfirm action taken: {base_url.rstrip('/')}/c/{token}"


def status(school: dict, today: str) -> str:
    """acted | escalated | pending | clear | unchecked, for the given day."""
    if school.get("last_alert_date") == today and school.get("alert_token"):
        if school.get("ack_date") == today:
            return "acted"
        if school.get("escalated_date") == today:
            return "escalated"
        return "pending"
    return "unchecked" if school.get("last_aqi") is None else "clear"


def pending_schools(schools: list, today: str) -> list:
    return [s for s in schools if status(s, today) == "pending"]


def escalation_message(schools: list) -> str:
    names = ", ".join(s["name"] for s in schools[:8])
    more = f" (+{len(schools) - 8} more)" if len(schools) > 8 else ""
    return (
        f"ESCALATION: {len(schools)} school(s) have not confirmed action on today's "
        f"AQI alert: {names}{more}."
    )


def recipients(school: dict) -> list:
    phones = [school.get("phone", "")] + list(school.get("contacts") or [])
    return [p for p in phones if p]
