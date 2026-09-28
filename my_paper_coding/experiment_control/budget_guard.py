#!/usr/bin/env python3
"""Budget preflight for a planned experiment. It never starts an API call."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--max-usd", type=float, required=True)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    ledger = json.loads(args.ledger.read_text(encoding="utf-8"))
    calls = int(manifest.get("planned_api_calls", 0))
    per_call = float(manifest.get("upper_bound_usd_per_call", ledger.get("max_single_run_usd", 0)))
    planned = calls * per_call
    already = float(ledger.get("total_cost_usd", 0))
    projected = already + planned
    status = "PASS" if planned <= args.max_usd and projected <= float(manifest.get("hard_stop_total_usd", args.max_usd)) else "BLOCKED"
    result = {"status": status, "planned_api_calls": calls, "upper_bound_usd_per_call": per_call, "planned_cost_usd": round(planned, 6), "already_spent_usd": round(already, 6), "projected_total_usd": round(projected, 6), "max_usd": args.max_usd, "hard_stop_total_usd": manifest.get("hard_stop_total_usd", args.max_usd), "network_calls_made": 0}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if status == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
