#!/usr/bin/env python3
"""Make a downstream decision solely from an upstream handoff."""
import argparse
import json
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("handoff", type=Path)
args = parser.parse_args()
handoff = json.loads(args.handoff.read_text(encoding="utf-8"))
action = "NO_RESTART" if handoff["reported_status"] == "healthy" else "RESTART"
print(json.dumps({"service": handoff["service"], "observed_status": handoff["reported_status"],
                  "action": action}, sort_keys=True))
