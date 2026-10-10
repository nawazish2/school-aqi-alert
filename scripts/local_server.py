"""Run the dashboard locally, no AWS needed: python scripts/local_server.py
Open http://localhost:8000. Data is in memory; SMS is printed, not sent.
"""
import json
import pathlib
import sys
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer

root = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root / "src"))

import advice  # noqa: E402
import aqi  # noqa: E402

SCHOOLS = {s["school_id"]: s for s in json.loads((root / "data" / "schools.json").read_text())}
ALERTS = []


def check(school, forced=None):
    try:
        value = forced if forced is not None else aqi.fetch_aqi(school["lat"], school["lon"])["aqi"]
    except Exception as exc:  # offline: fall back to a demo value
        print(f"AQI fetch failed ({exc}); using demo value")
        value = 180
    cat = aqi.category(value)
    msg = advice.build_message(school["name"], value, cat)
    now = datetime.now(timezone.utc).isoformat()
    school.update(last_aqi=value, last_category=cat, last_checked=now, last_message=msg)
    if value >= 151 or forced is not None:
        print("SMS ->", msg)
        ALERTS.insert(0, {"school_id": school["school_id"], "school": school["name"], "aqi": value,
                          "category": cat, "message": msg, "ts": now, "sms": "printed",
                          "simulated": forced is not None})
    return {"school_id": school["school_id"], "aqi": value, "category": cat, "message": msg, "sms": "printed"}


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
            self._send(list(SCHOOLS.values()))
        elif self.path == "/api/alerts":
            self._send(ALERTS[:20])
        else:
            self._send({"error": "not found"}, code=404)

    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("content-length") or 0) or 0) or b"{}"
        if self.path == "/api/refresh":
            self._send([check(s) for s in SCHOOLS.values()])
        elif self.path == "/api/simulate":
            req = json.loads(body)
            school = SCHOOLS.get(req.get("school_id"))
            if not school:
                return self._send({"error": "unknown school"}, code=404)
            self._send(check(school, int(req["aqi"])))
        else:
            self._send({"error": "not found"}, code=404)


if __name__ == "__main__":
    print("Dashboard: http://localhost:8000")
    HTTPServer(("127.0.0.1", 8000), H).serve_forever()
