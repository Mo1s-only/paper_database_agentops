#!/usr/bin/env python3
"""Read a route and invoke the existing controlled faulty inventory tool."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("route", type=Path)
    args = parser.parse_args()
    route = json.loads(args.route.read_text(encoding="utf-8"))
    faulty = Path(__file__).resolve().parent.parent / "failure_pilot" / "fake_inventory.py"
    process = subprocess.run([sys.executable, str(faulty), str(route["item"])],
                             capture_output=True, text=True, check=True)
    observed = json.loads(process.stdout)
    print(json.dumps({"item": route["item"], "required_available": route["required_available"],
                      "observed_available": observed["available"],
                      "satisfied": observed["available"] >= route["required_available"],
                      "inventory_status": observed["status"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
