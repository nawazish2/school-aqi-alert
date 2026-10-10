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
    sms_status = (
        _send_sms(school.get("phone", ""), message) if decision["should_alert"] else "not_needed"
    )

    update = (
        "SET last_aqi=:a, last_category=:c, last_checked=:t, last_message=:m, "
        "last_current=:cu, last_peak=:pk, last_hourly=:h"
    )
    values = {
        ":a": value, ":c": cat, ":t": now.isoformat(), ":m": message,
        ":cu": reading["current"], ":pk": reading["peak"], ":h": reading["hourly"],
    }
    if sms_status == "sent":
        update += ", last_alert_date=:d"
        values[":d"] = today
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


def to_jsonable(obj):
    if isinstance(obj, Decimal):
        return int(obj) if obj == obj.to_integral_value() else float(obj)
    raise TypeError(type(obj))
