"""Run the dashboard locally, no AWS needed: python3 scripts/local_server.py [port]
Open http://127.0.0.1:8000. Data is in memory; SMS is printed, not sent.
"""
import json
import pathlib
import sys
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer

root = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root / "src"))

import aqi  # noqa: E402
import logic  # noqa: E402

THRESHOLD = 151
PORT = 8000
TODAY = lambda: datetime.now(timezone.utc).date().isoformat()  # noqa: E731
SCHOOLS = {s["school_id"]: s for s in json.loads((root / "data" / "schools.json").read_text())}
ALERTS = []


def check(school, forced=None):
    try:
        reading = logic.forced_reading(forced) if forced is not None else aqi.fetch_aqi(school["lat"], school["lon"])
    except Exception as exc:  # offline: fall back to a demo value
        print(f"AQI fetch failed ({exc}); using demo value")
        reading = {**logic.forced_reading(180), "hourly": [150, 160, 175, 180, 190, 185, 170, 160]}
    now = datetime.now(timezone.utc)
    d = logic.evaluate(school, reading, THRESHOLD, now.date().isoformat(), forced=forced is not None)
    school.update(
        last_aqi=d["aqi"], last_category=d["category"], last_checked=now.isoformat(),
        last_message=d["message"], last_current=reading["current"], last_peak=reading["peak"],
        last_hourly=reading["hourly"],
    )
    sms = "not_needed"
    if d["should_alert"]:
        token = logic.new_token(school["school_id"])
        d["message"] = logic.with_confirm_link(d["message"], f"http://127.0.0.1:{PORT}", token)
        school["last_message"] = d["message"]
        print("SMS ->", d["message"])
        sms = "printed"
        school.update(last_alert_date=now.date().isoformat(), alert_token=token)
        school.pop("ack_date", None)
        school.pop("escalated_date", None)
        ALERTS.insert(0, {"school_id": school["school_id"], "school": school["name"], "aqi": d["aqi"],
                          "category": d["category"], "message": d["message"], "ts": now.isoformat(),
                          "sms": sms, "simulated": forced is not None})
    return {"school_id": school["school_id"], "aqi": d["aqi"], "category": d["category"],
            "message": d["message"], "sms": sms}


class H(BaseHTTPRequestHandler):
    def _send(self, body, ctype="application/json", code=200):
        data = body.encode() if isinstance(body, str) else json.dumps(body).encode()
        self.send_response(code)
        self.send_header("content-type", ctype)
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self._send((root / "src" / "dashboard.html").read_text(encoding="utf-8"), "text/html; charset=utf-8")
        elif self.path == "/api/schools":
            self._send([{**s, "status": logic.status(s, TODAY())} for s in SCHOOLS.values()])
        elif self.path.startswith("/c/"):
            token = self.path[3:]
            school = SCHOOLS.get(logic.school_id_from_token(token))
            if school and school.get("alert_token") == token:
                school["ack_date"] = TODAY()
                self._send(f"<meta charset=utf-8><h2 style='font-family:system-ui;text-align:center;margin-top:20vh'>✅ Thank you. {school['name']} has confirmed action.</h2>", "text/html; charset=utf-8")
            else:
                self._send("<h2>Link not valid</h2>", "text/html; charset=utf-8", 404)
        elif self.path == "/api/alerts":
            self._send(ALERTS[:20])
        else:
            self._send({"error": "not found"}, code=404)

    def do_DELETE(self):
        if self.path.startswith("/api/schools/"):
            SCHOOLS.pop(self.path.rsplit("/", 1)[1], None)
            return self._send({"deleted": True})
        self._send({"error": "not found"}, code=404)

    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("content-length") or 0)) or b"{}"
        if self.path == "/api/refresh":
            self._send([check(s) for s in list(SCHOOLS.values())])
        elif self.path == "/api/escalate":
            pending = logic.pending_schools(list(SCHOOLS.values()), TODAY())
            for p in pending:
                p["escalated_date"] = TODAY()
            if pending:
                msg = logic.escalation_message(pending)
                print("SMS to officer ->", msg)
                ALERTS.insert(0, {"school_id": "*", "school": "District officer", "aqi": 0, "category": "Escalation",
                                  "message": msg, "ts": datetime.now(timezone.utc).isoformat(), "sms": "printed", "simulated": False})
            self._send({"escalated": len(pending), "schools": [p["name"] for p in pending]})
        elif self.path == "/api/simulate":
            req = json.loads(body)
            school = SCHOOLS.get(req.get("school_id"))
            if not school:
                return self._send({"error": "unknown school"}, code=404)
            self._send(check(school, int(req["aqi"])))
        elif self.path == "/api/schools":
            try:
                school = logic.validate_school(json.loads(body))
            except ValueError as exc:
                return self._send({"error": str(exc)}, code=400)
            SCHOOLS[school["school_id"]] = school
            check(school)
            self._send(school)
        else:
            self._send({"error": "not found"}, code=404)


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    PORT = port
    print(f"Dashboard: http://127.0.0.1:{port}  (Ctrl+C to stop)")
    HTTPServer(("0.0.0.0", port), H).serve_forever()
