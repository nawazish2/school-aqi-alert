"""Scheduled Lambda: check every school and alert where air is bad."""
import json

import core


def handler(event, context):
    schools_table, _ = core._tables()
    schools = schools_table.scan()["Items"]
    results = []
    for school in schools:
        try:
            results.append(core.process_school(school))
        except Exception as exc:  # one failing school must not stop the rest
            print(f"{school.get('school_id')} failed: {exc}")
            results.append({"school_id": school.get("school_id"), "error": str(exc)})
    print(json.dumps(results, default=core.to_jsonable))
    return {"checked": len(schools)}
