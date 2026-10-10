"""No-AWS demo: fetch live AQI for each school and print the alert text."""
import json
import pathlib
import sys

root = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root / "src"))

import advice  # noqa: E402
import aqi  # noqa: E402

for s in json.loads((root / "data" / "schools.json").read_text()):
    r = aqi.fetch_aqi(s["lat"], s["lon"])
    print(advice.build_message(s["name"], r["aqi"], aqi.category(r["aqi"])))
