"""HTTP API + dashboard (single Lambda behind an HTTP API)."""
import json
import os

import core

HERE = os.path.dirname(__file__)


def _resp(status, body, content_type="application/json"):
    if content_type == "application/json":
        body = json.dumps(body, default=core.to_jsonable)
    return {"statusCode": status, "headers": {"content-type": content_type}, "body": body}


def handler(event, context):
    route = event.get("routeKey", "")
    schools_table, alerts_table = core._tables()

    if route == "GET /":
        with open(os.path.join(HERE, "dashboard.html"), encoding="utf-8") as f:
            return _resp(200, f.read(), "text/html; charset=utf-8")

    if route == "GET /api/schools":
        return _resp(200, schools_table.scan()["Items"])

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
