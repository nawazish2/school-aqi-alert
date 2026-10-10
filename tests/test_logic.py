import os
import sys
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import advice  # noqa: E402
import aqi  # noqa: E402


def test_category_bands():
    assert aqi.category(0) == "Good"
    assert aqi.category(50) == "Good"
    assert aqi.category(51) == "Moderate"
    assert aqi.category(151) == "Unhealthy"
    assert aqi.category(320) == "Hazardous"


def test_rule_advice_escalates():
    assert "Normal" in advice.rule_advice(30)
    assert "Cancel outdoor" in advice.rule_advice(180)
    assert "closing school" in advice.rule_advice(400)


def test_message_has_school_and_aqi():
    msg = advice.build_message("DPS", 320, aqi.category(320))
    assert "DPS" in msg and "320" in msg and len(msg) <= 300


def test_agent_failure_falls_back_to_rules():
    with mock.patch.dict(os.environ, {"ADVICE_MODEL_ID": "x"}), mock.patch.object(
        advice, "_agent_advice", side_effect=RuntimeError("boom")
    ):
        msg = advice.build_message("DPS", 180, "Unhealthy")
    assert "Cancel outdoor" in msg
