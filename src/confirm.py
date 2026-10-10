"""Function URL: a principal taps the link in the SMS to confirm the school acted."""
import html

import core

PAGE = """<!doctype html><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>{title}</title><body style="font:18px system-ui;max-width:420px;margin:15vh auto;padding:0 20px;text-align:center">
<div style="font-size:56px">{icon}</div><h2>{title}</h2><p>{body}</p></body>"""


def handler(event, context):
    token = (event.get("rawPath") or "").rsplit("/", 1)[-1]
    name = core.confirm(token) if token else None
    if name:
        page = PAGE.format(icon="✅", title="Thank you", body=f"Recorded: {html.escape(name)} has acted on today's air-quality alert.")
        status = 200
    else:
        page = PAGE.format(icon="⚠️", title="Link not valid", body="This confirmation link is invalid or has been replaced by a newer alert.")
        status = 404
    return {"statusCode": status, "headers": {"content-type": "text/html; charset=utf-8"}, "body": page}
