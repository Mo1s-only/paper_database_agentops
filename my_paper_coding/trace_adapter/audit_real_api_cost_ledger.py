#!/usr/bin/env python3
"""Reconcile recorded CLI costs after a frozen API ledger without making calls."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re

from align_candidates import ROOT, write_json


RUN_ROOT = ROOT / "lab" / "experiment" / "experiment_20261021_24_agentsight_candidate_mock"
LEDGER = ROOT / "my_paper_coding" / "experiment_control" / "cost-ledger-through-run12-20261021.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def extract_cost(run_dir: Path) -> dict | None:
    candidates = (
        (run_dir / "diagnostic-summary.json", "diagnostic-summary"),
        (run_dir / "capture-summary.json", "capture-summary"),
        (run_dir / "agent_a-capture-summary.json", "agent_a-capture-summary"),
    )
    for path, kind in candidates:
        if not path.is_file():
            continue
        value = json.loads(path.read_text(encoding="utf-8"))
        if kind == "diagnostic-summary":
            reported_cost = (value.get("cli") or {}).get("reported_cost_usd")
            sessions = value.get("sessions")
            cost_complete = reported_cost is not None
            real_api = value.get("real_api") is True
            scenario = (json.loads((run_dir / "plan.json").read_text(encoding="utf-8"))
                        .get("scenario") if (run_dir / "plan.json").is_file() else None)
        elif kind == "capture-summary":
            reported_cost = value.get("reported_cost_usd")
            sessions = value.get("actual_cli_sessions")
            cost_complete = value.get("cost_complete") is True and reported_cost is not None
            real_api = sessions is not None and sessions > 0 and cost_complete
            scenario = value.get("scenario")
        else:
            reported_cost = value.get("reported_cost_usd")
            sessions = 1
            cost_complete = reported_cost is not None
            real_api = cost_complete
            scenario = None
        return {
            "run_id": run_dir.name,
            "scenario": scenario,
            "sessions": sessions,
            "cost_summary_kind": kind,
            "reported_cost_usd": reported_cost,
            "cost_complete": cost_complete,
            "real_api_evidence": real_api,
            "cost_summary_path": path.relative_to(ROOT).as_posix(),
            "cost_summary_sha256": sha256_file(path),
        }
    return None


def reconcile(ledger_path: Path = LEDGER, run_root: Path = RUN_ROOT) -> dict:
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    runs = []
    unresolved = []
    candidates = sorted(run_root.glob("real-canary-2026102*-*"))
    for directory in candidates:
        if not directory.is_dir():
            continue
        match = re.fullmatch(r"real-canary-(20261021|20261022)-(\d+)", directory.name)
        if not match or (match.group(1) == "20261021" and int(match.group(2)) <= 12):
            continue
        row = extract_cost(directory)
        if row is None:
            unresolved.append(directory.relative_to(ROOT).as_posix())
        else:
            runs.append(row)
    reported_costs = [row["reported_cost_usd"] for row in runs
                      if row["cost_complete"] and isinstance(row["reported_cost_usd"], (int, float))]
    incomplete = [row["run_id"] for row in runs if not row["cost_complete"]]
    total = round(sum(reported_costs), 10)
    old_total = float(ledger["total_cost_usd"])
    hard_stop = float(ledger["authorized_hard_stop_total_usd"])
    projected_total = round(old_total + total, 10)
    return {
        "schema_version": "agentops-real-api-cost-reconciliation-v0.1",
        "source_ledger": {
            "path": ledger_path.relative_to(ROOT).as_posix(),
            "sha256": sha256_file(ledger_path),
            "label": "through-run12",
            "reported_total_usd": old_total,
            "authorized_hard_stop_usd": hard_stop,
            "remaining_usd_in_source_ledger": ledger.get("remaining_to_hard_stop_usd"),
        },
        "later_run_count_with_cost_summary": len(runs),
        "later_runs": runs,
        "unresolved_run_directories": unresolved,
        "runs_with_incomplete_cost": incomplete,
        "later_reported_cost_usd": total,
        "later_reported_cost_cny_at_10_usd_cny": round(total * 10, 6),
        "projected_total_if_later_runs_are_additive_usd": projected_total,
        "excess_over_source_ledger_hard_stop_usd_if_additive": round(max(0, projected_total - hard_stop), 10),
        "new_user_cap_cny": 1.0,
        "invoice_reconciled": False,
        "api_requests_during_reconciliation": 0,
        "interpretation": "CLI-reported evidence; run inclusion and provider invoice remain to be reconciled before another paid call.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", type=Path, default=LEDGER)
    parser.add_argument("--run-root", type=Path, default=RUN_ROOT)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error(f"Refusing to replace existing reconciliation report: {args.output}")
    report = reconcile(args.ledger, args.run_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    write_json(args.output, report)
    print(json.dumps({"runs": report["later_run_count_with_cost_summary"],
                      "reported_usd": report["later_reported_cost_usd"],
                      "unresolved": len(report["unresolved_run_directories"]),
                      "api_requests": 0}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
