#!/usr/bin/env python3
"""Execute the chosen route without consulting the hidden evaluation truth."""
import argparse
import json
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("route", type=Path)
args = parser.parse_args()
route = json.loads(args.route.read_text(encoding="utf-8"))
capabilities = set(route["selected_capabilities"])
retrieved = "retrieval" in capabilities
print(json.dumps({"task": route["task"], "executed_role": route["selected_role"],
                  "retrieved": retrieved, "answer": "document-42" if retrieved else None}, sort_keys=True))
