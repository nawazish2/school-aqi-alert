"""HTTP API + dashboard (single Lambda behind an HTTP API)."""
import json
import os
from decimal import Decimal

import core
import logic

HERE = os.path.dirname(__file__)


def _resp(status, body, content_type="application/json"):
    if content_type == "application/json":
        body = json.dumps(body, default=core.to_jsonable)
    return {"statusCode": status, "headers": {"content-type": content_type}, "body": body}


def _authorized(event) -> bool:
    key = os.environ.get("ADMIN_KEY", "")
    return not key or (event.get("headers") or {}).get("x-admin-key") == key


def handler(event, context):
    route = event.get("routeKey", "")
    if route.startswith(("POST", "DELETE")) and not _authorized(event):
        return _resp(401, {"error": "admin key required"})
    schools_table, alerts_table = core._tables()

    if route == "GET /":
        with open(os.path.join(HERE, "dashboard.html"), encoding="utf-8") as f:
            return _resp(200, f.read(), "text/html; charset=utf-8")

    if route == "GET /api/schools":
        return _resp(200, schools_table.scan()["Items"])

    if route == "POST /api/schools":
        try:
            school = logic.validate_school(json.loads(event.get("body") or "{}"))
        except (ValueError, json.JSONDecodeError) as exc:
            return _resp(400, {"error": str(exc)})
        item = {**school, "lat": Decimal(str(school["lat"])), "lon": Decimal(str(school["lon"]))}
        schools_table.put_item(Item=item)
        try:  # first reading right away so the card is never empty
            core.process_school(item)
        except Exception as exc:
            print(f"first check failed for {item['school_id']}: {exc}")
        return _resp(200, schools_table.get_item(Key={"school_id": item["school_id"]})["Item"])

    if route == "DELETE /api/schools/{school_id}":
        schools_table.delete_item(Key={"school_id": event["pathParameters"]["school_id"]})
        return _resp(200, {"deleted": True})

    if route == "GET /api/alerts":
        items = alerts_table.query(
            KeyConditionExpression="pk = :p",
            ExpressionAttributeValues={":p": "ALERT"},
            ScanIndexForward=False,
            Limit=20,
        )["Items"]
        return _resp(200, items)

    if route == "POST /api/refresh":
        results = []
        for school in schools_table.scan()["Items"]:
            try:
                results.append(core.process_school(school))
            except Exception as exc:
                results.append({"school_id": school["school_id"], "error": str(exc)})
        return _resp(200, results)

    if route == "POST /api/simulate":
        try:
            body = json.loads(event.get("body") or "{}")
            school_id, value = body["school_id"], int(body["aqi"])
        except (ValueError, KeyError):
            return _resp(400, {"error": "need school_id and integer aqi"})
        if not 0 <= value <= 500:
            return _resp(400, {"error": "aqi must be 0-500"})
        school = schools_table.get_item(Key={"school_id": school_id}).get("Item")
        if not school:
            return _resp(404, {"error": "unknown school"})
        return _resp(200, core.process_school(school, forced_aqi=value))

    return _resp(404, {"error": "not found"})
