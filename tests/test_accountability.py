import os
import sys
from unittest import mock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
os.environ.update(SCHOOLS_TABLE="s", ALERTS_TABLE="a")

import core  # noqa: E402
import logic  # noqa: E402

TODAY = "2026-10-10"


def test_token_roundtrip():
    token = logic.new_token("dps-rkp")
    assert logic.school_id_from_token(token) == "dps-rkp"
    assert logic.school_id_from_token("garbage") == ""


def test_status_lifecycle():
    s = {"school_id": "x"}
    assert logic.status(s, TODAY) == "unchecked"
    s["last_aqi"] = 80
    assert logic.status(s, TODAY) == "clear"
    s.update(last_alert_date=TODAY, alert_token="t")
    assert logic.status(s, TODAY) == "pending"
    assert logic.status({**s, "escalated_date": TODAY}, TODAY) == "escalated"
    assert logic.status({**s, "ack_date": TODAY}, TODAY) == "acted"
    # yesterday's alert says nothing about today
    assert logic.status({**s, "last_alert_date": "2026-10-09"}, TODAY) == "clear"


def test_confirm_link_and_escalation_text():
    assert logic.with_confirm_link("hi", "", "t") == "hi"
    assert logic.with_confirm_link("hi", "https://x.test/", "t").endswith("https://x.test/c/t")
    msg = logic.escalation_message([{"name": f"S{i}"} for i in range(10)])
    assert "10 school(s)" in msg and "+2 more" in msg


def test_contacts_validation_and_recipients():
    ok = logic.validate_school({"name": "Okay", "lat": 1, "lon": 1, "phone": "+911234567890",
                                "contacts": "+919876543210, +919000000000"})
    assert len(ok["contacts"]) == 2 and len(logic.recipients(ok)) == 3
    with pytest.raises(ValueError):
        logic.validate_school({"name": "Okay", "lat": 1, "lon": 1, "contacts": "12345"})


def tables(item):
    schools, alerts = mock.Mock(), mock.Mock()
    schools.get_item.return_value = {"Item": item} if item else {}
    return schools, alerts


def test_confirm_marks_acted_only_for_matching_token():
    item = {"school_id": "x", "name": "X School", "alert_token": "x.abc"}
    schools, alerts = tables(item)
    with mock.patch.object(core, "_tables", return_value=(schools, alerts)):
        assert core.confirm("x.wrong") is None
        assert not schools.update_item.called
        assert core.confirm("x.abc") == "X School"
        assert schools.update_item.called


def test_escalate_only_pending_schools():
    today = core.datetime.now(core.timezone.utc).date().isoformat()
    pending = {"school_id": "a", "name": "A", "last_alert_date": today, "alert_token": "t"}
    acted = {"school_id": "b", "name": "B", "last_alert_date": today, "alert_token": "t", "ack_date": today}
    schools, alerts = mock.Mock(), mock.Mock()
    schools.scan.return_value = {"Items": [pending, acted]}
    with mock.patch.object(core, "_tables", return_value=(schools, alerts)), mock.patch.object(
        core, "_send_sms", return_value="sent"
    ) as sms, mock.patch.dict(os.environ, {"OFFICER_PHONE": "+911111111111"}):
        out = core.escalate()
    assert out["escalated"] == 1 and out["schools"] == ["A"] and sms.call_count == 1
    assert schools.update_item.call_count == 1
