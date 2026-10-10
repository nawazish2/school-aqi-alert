import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import advice  # noqa: E402
import aqi  # noqa: E402
import logic  # noqa: E402


def sample(current=90, peak_hour_value=260):
    times = [f"2026-10-10T{h:02d}:00" for h in range(24)] + [f"2026-10-11T{h:02d}:00" for h in range(24)]
    values = [80] * 48
    values[10] = peak_hour_value  # 10:00 today, inside school hours
    values[3] = 400  # 03:00 today, before school: must be ignored
    return {
        "current": {"time": "2026-10-10T06:30", "us_aqi": current, "pm2_5": 40},
        "hourly": {"time": times, "us_aqi": values},
    }


def test_forecast_peak_drives_decision():
    r = aqi.parse_response(sample())
    assert r["current"] == 90 and r["peak"] == 260 and r["aqi"] == 260
    assert len(r["hourly"]) == 24 and 400 not in r["hourly"]


def test_current_wins_when_higher():
    r = aqi.parse_response(sample(current=300, peak_hour_value=120))
    assert r["aqi"] == 300


def test_hindi_and_both():
    hi = advice.build_message("DPS", 320, "Hazardous", "hi")
    assert "अलर्ट" in hi and "320" in hi
    both = advice.build_message("DPS", 320, "Hazardous", "both")
    assert "AQI Alert" in both and "अलर्ट" in both and "\n" in both


def test_evaluate_threshold_and_dedupe():
    school = {"name": "S", "lang": "en"}
    assert logic.evaluate(school, logic.forced_reading(200), 151, "d")["should_alert"]
    assert not logic.evaluate(school, logic.forced_reading(100), 151, "d")["should_alert"]
    again = {**school, "last_alert_date": "d"}
    assert not logic.evaluate(again, logic.forced_reading(200), 151, "d")["should_alert"]
    assert logic.evaluate(again, logic.forced_reading(200), 151, "d", forced=True)["should_alert"]


def test_validate_school():
    ok = logic.validate_school({"name": "My School!", "lat": "28.6", "lon": "77.2", "phone": "+91 98765 43210", "lang": "both"})
    assert ok["school_id"] == "my-school" and ok["phone"] == "+919876543210"
    for bad in (
        {"name": "x", "lat": 1, "lon": 1},
        {"name": "Okay", "lat": 99, "lon": 1},
        {"name": "Okay", "lat": 1, "lon": 1, "phone": "98765"},
        {"name": "Okay", "lat": 1, "lon": 1, "lang": "fr"},
        {"name": "Okay", "lat": "abc", "lon": 1},
    ):
        with pytest.raises(ValueError):
            logic.validate_school(bad)
