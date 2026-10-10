"""Scheduled Lambda: escalate unconfirmed alerts to the district officer."""
import json

import core


def handler(event, context):
    result = core.escalate()
    print(json.dumps(result))
    return result
