"""Check one school: fetch AQI, build advice, store the result, send the SMS."""
import os
from datetime import datetime, timezone
from decimal import Decimal

import boto3

import aqi as aqi_mod
import logic

_ddb = None
_sns = None


def _tables():
    global _ddb
    if _ddb is None:
        _ddb = boto3.resource("dynamodb")
    return _ddb.Table(os.environ["SCHOOLS_TABLE"]), _ddb.Table(os.environ["ALERTS_TABLE"])


def _send_sms(phone: str, message: str) -> str:
    global _sns
    if not phone:
        return "no_phone"
    if _sns is None:
        _sns = boto3.client("sns")
    try:
        _sns.publish(
            PhoneNumber=phone,
            Message=message,
            MessageAttributes={
                "AWS.SNS.SMS.SMSType": {"DataType": "String", "StringValue": "Transactional"}
            },
        )
        return "sent"
    except Exception as exc:
        print(f"sms failed for {phone}: {exc}")
        return "failed"


def _send_all(phones: list, message: str) -> str:
    """sent if any recipient got it, failed if all failed, no_phone if nobody to text."""
    if not phones:
        return "no_phone"
    results = [_send_sms(p, message) for p in phones]
    return "sent" if "sent" in results else "failed"


def process_school(school: dict, forced_aqi: int | None = None) -> dict:
    """forced_aqi is used by the demo 'simulate' button; it always sends."""
    schools, alerts = _tables()
    threshold = int(os.environ.get("ALERT_THRESHOLD", "151"))
    now = datetime.now(timezone.utc)
    today = now.date().isoformat()

    if forced_aqi is not None:
        reading = logic.forced_reading(int(forced_aqi))
    else:
        reading = aqi_mod.fetch_aqi(float(school["lat"]), float(school["lon"]))

    decision = logic.evaluate(school, reading, threshold, today, forced=forced_aqi is not None)
    value, cat, message = decision["aqi"], decision["category"], decision["message"]
    token = None
    sms_status = "not_needed"
    if decision["should_alert"]:
        token = logic.new_token(school["school_id"])
        message = logic.with_confirm_link(message, os.environ.get("CONFIRM_BASE_URL", ""), token)
        sms_status = _send_all(logic.recipients(school), message)

    update = (
        "SET last_aqi=:a, last_category=:c, last_checked=:t, last_message=:m, "
        "last_current=:cu, last_peak=:pk, last_hourly=:h"
    )
    values = {
        ":a": value, ":c": cat, ":t": now.isoformat(), ":m": message,
        ":cu": reading["current"], ":pk": reading["peak"], ":h": reading["hourly"],
    }
    remove = ""
    if token and sms_status in ("sent", "no_phone"):
        update += ", last_alert_date=:d, alert_token=:tok"
        values[":d"] = today
        values[":tok"] = token
        remove = " REMOVE ack_date, escalated_date"
    update += remove
    schools.update_item(
        Key={"school_id": school["school_id"]},
        UpdateExpression=update,
        ExpressionAttributeValues=values,
    )

    if decision["should_alert"]:
        alerts.put_item(
            Item={
                "pk": "ALERT",
                "ts": now.isoformat(),
                "school_id": school["school_id"],
                "school": school["name"],
                "aqi": value,
                "category": cat,
                "message": message,
                "sms": sms_status,
                "simulated": forced_aqi is not None,
            }
        )
    return {
        "school_id": school["school_id"],
        "aqi": value,
        "category": cat,
        "message": message,
        "sms": sms_status,
    }


def confirm(token: str) -> str | None:
    """Principal tapped the link: record that the school acted. Returns school name."""
    schools, _ = _tables()
    school_id = logic.school_id_from_token(token)
    if not school_id:
        return None
    school = schools.get_item(Key={"school_id": school_id}).get("Item")
    if not school or school.get("alert_token") != token:
        return None
    today = datetime.now(timezone.utc).date().isoformat()
    schools.update_item(
        Key={"school_id": school_id},
        UpdateExpression="SET ack_date=:d, ack_ts=:t",
        ExpressionAttributeValues={":d": today, ":t": datetime.now(timezone.utc).isoformat()},
    )
    return school["name"]


def escalate() -> dict:
    """Text the district officer about schools that were alerted but never confirmed."""
    schools, alerts = _tables()
    now = datetime.now(timezone.utc)
    today = now.date().isoformat()
    pending = logic.pending_schools(schools.scan()["Items"], today)
    if not pending:
        return {"escalated": 0, "schools": [], "sms": "not_needed"}
    message = logic.escalation_message(pending)
    officer = os.environ.get("OFFICER_PHONE", "")
    sms_status = _send_sms(officer, message) if officer else "no_officer"
    for s in pending:
        schools.update_item(
            Key={"school_id": s["school_id"]},
            UpdateExpression="SET escalated_date=:d",
            ExpressionAttributeValues={":d": today},
        )
    alerts.put_item(
        Item={
            "pk": "ALERT", "ts": now.isoformat(), "school_id": "*", "school": "District officer",
            "aqi": 0, "category": "Escalation", "message": message, "sms": sms_status,
            "simulated": False,
        }
    )
    return {"escalated": len(pending), "schools": [s["name"] for s in pending], "sms": sms_status}


def to_jsonable(obj):
    if isinstance(obj, Decimal):
        return int(obj) if obj == obj.to_integral_value() else float(obj)
    raise TypeError(type(obj))
