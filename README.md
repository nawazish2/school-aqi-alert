# School AQI Alert

Texts a school principal at 6:30 AM when the air is bad, with a clear action ("Cancel outdoor PT").

**Flow:** EventBridge -> Lambda (Open-Meteo AQI) -> advice (rules, optional Strands agent on Bedrock) -> SNS SMS -> DynamoDB -> dashboard served by an API Lambda.

## Run without AWS
    python scripts/local_server.py    # dashboard at http://127.0.0.1:8000 (pass another port: `python scripts/local_server.py 8080`) (SMS printed in terminal)
    pip install pytest boto3
    python -m pytest tests
    python scripts/local_demo.py      # live AQI + alert text for each school

## Deploy
    sam build && sam deploy --guided
    python3 scripts/seed.py <SchoolsTableName> +91XXXXXXXXXX   # your verified phone (or add schools from the dashboard)
Open the `DashboardUrl` output. Use "Simulate bad AQI" for the demo.

## Accountability loop
1. Alert SMS goes to the principal and any extra contacts, with a **confirm link**.
2. The principal taps it: the school shows as **Acted**. Nothing to install, works on any phone.
3. At 7:30 AM IST, schools that have not confirmed are reported to the **district officer** (`OfficerPhone` deploy parameter).
4. The dashboard shows Acted / Awaiting / Escalated for the day. "Run 7:30 escalation now" triggers it for demos.

## Features
- Alerts use the **school-hours forecast** (worse of now and today's 7am-4pm peak), so principals are warned about the day ahead.
- SMS in **English, Hindi or both** per school.
- Dashboard: stats, 24h forecast sparkline per school, add schools by clicking the map, alert history.
- Optional `AdminKey` deploy parameter protects add/remove/refresh/simulate (`--parameter-overrides AdminKey=secret OfficerPhone=+91XXXXXXXXXX`).

## Notes
- SMS: new accounts are in the SNS SMS sandbox, so verify your phone number in SNS first. India also needs sender registration for production.
- Advice agent: deploy with `--parameter-overrides AdviceModelId=<bedrock model id>` after enabling model access. Empty = rule-based.
- The dashboard has no auth; fine for a demo, add Cognito before real use.
