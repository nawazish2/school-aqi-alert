"""Load data/schools.json into the Schools table.

Usage: python scripts/seed.py <SchoolsTableName> [+91XXXXXXXXXX]
The optional phone number is applied to every school (use your own for the demo).
"""
import json
import pathlib
import sys
from decimal import Decimal

import boto3

table_name = sys.argv[1]
phone = sys.argv[2] if len(sys.argv) > 2 else None
path = pathlib.Path(__file__).resolve().parent.parent / "data" / "schools.json"
schools = json.loads(path.read_text(), parse_float=Decimal)

table = boto3.resource("dynamodb").Table(table_name)
for s in schools:
    if phone:
        s["phone"] = phone
    table.put_item(Item=s)
print(f"seeded {len(schools)} schools into {table_name}")
