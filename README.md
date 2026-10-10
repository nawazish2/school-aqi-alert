# School AQI Alert

Texts a school principal at 6:30 AM when the air is bad, with a clear action ("Cancel outdoor PT").

**Flow:** EventBridge -> Lambda (Open-Meteo AQI) -> advice (rules, optional Strands agent on Bedrock) -> SNS SMS -> DynamoDB -> dashboard served by an API Lambda.

## Run without AWS
    python scripts/local_server.py    # dashboard at http://localhost:8000 (SMS printed in terminal)
    pip install pytest boto3
    python -m pytest tests
    python scripts/local_demo.py      # live AQI + alert text for each school

## Deploy
    sam build && sam deploy --guided
    python scripts/seed.py <SchoolsTableName> +91XXXXXXXXXX   # your verified phone
Open the `DashboardUrl` output. Use "Simulate bad AQI" for the demo.

## Notes
- SMS: new accounts are in the SNS SMS sandbox, so verify your phone number in SNS first. India also needs sender registration for production.
- Advice agent: deploy with `--parameter-overrides AdviceModelId=<bedrock model id>` after enabling model access. Empty = rule-based.
- The dashboard has no auth; fine for a demo, add Cognito before real use.
