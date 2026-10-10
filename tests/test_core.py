import os
import sys
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

os.environ.update(SCHOOLS_TABLE="s", ALERTS_TABLE="a", ALERT_THRESHOLD="151")

import core  # noqa: E402

SCHOOL = {"school_id": "x", "name": "Test School", "lat": 1, "lon": 2, "phone": "+911234567890"}


def run(school, forced=None, aqi_value=200):
    schools, alerts = mock.Mock(), mock.Mock()
    with mock.patch.object(core, "_tables", return_value=(schools, alerts)), mock.patch.object(
        core.aqi_mod, "fetch_aqi", return_value={"aqi": aqi_value, "pm25": 1}
    ), mock.patch.object(core, "_send_sms", return_value="sent") as sms:
        out = core.process_school(school, forced_aqi=forced)
    return out, sms, alerts


def test_bad_air_sends_sms_and_logs_alert():
    out, sms, alerts = run(SCHOOL)
    assert out["sms"] == "sent" and sms.called and alerts.put_item.called


def test_good_air_sends_nothing():
    out, sms, alerts = run(SCHOOL, aqi_value=40)
    assert out["sms"] == "not_needed" and not sms.called and not alerts.put_item.called


def test_no_duplicate_alert_same_day():
    today = core.datetime.now(core.timezone.utc).date().isoformat()
    out, sms, _ = run({**SCHOOL, "last_alert_date": today})
    assert out["sms"] == "not_needed" and not sms.called


def test_simulate_always_sends():
    today = core.datetime.now(core.timezone.utc).date().isoformat()
    out, sms, _ = run({**SCHOOL, "last_alert_date": today}, forced=320)
    assert out["aqi"] == 320 and sms.called
