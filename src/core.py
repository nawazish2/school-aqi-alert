"""Check one school: fetch AQI, build advice, store the result, send the SMS."""
import os
from datetime import datetime, timezone
from decimal import Decimal

import boto3

import advice
import aqi as aqi_mod

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
        reading = {"aqi": int(forced_aqi), "pm25": None}
    else:
        reading = aqi_mod.fetch_aqi(float(school["lat"]), float(school["lon"]))

    value = reading["aqi"]
    cat = aqi_mod.category(value)
    message = advice.build_message(school["name"], value, cat)

    should_alert = value >= threshold and (
        forced_aqi is not None or school.get("last_alert_date") != today
    )
    sms_status = _send_sms(school.get("phone", ""), message) if should_alert else "not_needed"

    update = "SET last_aqi=:a, last_category=:c, last_checked=:t, last_message=:m"
    values = {":a": value, ":c": cat, ":t": now.isoformat(), ":m": message}
    if sms_status == "sent":
        update += ", last_alert_date=:d"
        values[":d"] = today
    schools.update_item(
        Key={"school_id": school["school_id"]},
        UpdateExpression=update,
        ExpressionAttributeValues=values,
    )

    if should_alert:
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
