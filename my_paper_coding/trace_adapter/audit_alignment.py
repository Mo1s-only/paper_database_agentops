#!/usr/bin/env python3
"""Audit source references and run explicitly synthetic perturbations on real inputs."""
from __future__ import annotations

import argparse
from collections import Counter
import copy
import json
from pathlib import Path
import sqlite3

from align_candidates import ROOT, align, load_evidence, locator, pid, write_json


def raw_row(record: dict) -> dict:
    source = record["source"]
    table = source["table"]
    path = ROOT / source["path"]
    with sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True) as connection:
        connection.row_factory = sqlite3.Row
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if table not in tables:
            raise ValueError("Unknown table")
        quoted = '"' + table.replace('"', '""') + '"'
        columns = {row[1] for row in connection.execute(f"PRAGMA table_info({quoted})")}
        key = '"id"' if "id" in columns else "rowid"
        row = connection.execute(f"SELECT * FROM {quoted} WHERE {key} = ?", (source["row"],)).fetchone()
        if row is None:
            raise ValueError("Missing source row")
        return dict(row)


def audit(manifest_path: Path, evidence_path: Path) -> dict:
    manifest, records, frozen = load_evidence(manifest_path, evidence_path)
    decisions, _, summary = align(records, manifest["run_id"])
    indexed = {locator(r): r for r in records}
    checks = []
    # Direct raw-SQLite consistency checks, not independent causal or alignment labels.
    for item in decisions:
        if item["status"] != "accepted" or not (item["relation"].endswith("_process") or item["relation"] == "process_parent"):
            continue
        source = indexed[item["source_ref"]]
        target_ref = item["candidates"][0]["target_ref"]
        target = indexed[target_ref]
        left, right = raw_row(source), raw_row(target)
        expected_pid = left.get("ppid") if item["relation"] == "process_parent" else left.get("pid", left.get("related_pid"))
        timestamp = left.get("timestamp_ms", left.get("start_timestamp_ms"))
        start, end = right.get("start_timestamp_ms"), right.get("end_timestamp_ms")
        passed = (expected_pid == right.get("pid") and timestamp is not None
                  and start is not None and end is not None and start <= timestamp <= end)
        checks.append({"association_id": item["association_id"], "passed": passed,
                       "evidence_refs": [item["source_ref"], target_ref]})

    perturbations = []
    for tool in (r for r in records if r["record_type"] == "agentsight.tool_calls"):
        source_ref = locator(tool)
        for treatment in ("remove_pid", "remove_timestamp", "shift_time", "duplicate_process"):
            modified = copy.deepcopy(records)
            subject = next(r for r in modified if locator(r) == source_ref)
            expected = "abstain" if treatment in {"remove_pid", "shift_time"} else "uncertain"
            if treatment == "remove_pid":
                subject["pid"] = None
                subject["fields"]["pid"] = None
                subject["fields"]["related_pid"] = None
            elif treatment == "remove_timestamp":
                subject["timestamp"] = None
            elif treatment == "shift_time":
                subject["timestamp"] = max(r.get("fields", {}).get("end_timestamp_ms") or 0 for r in modified) + 1000000
            else:
                matches = [r for r in modified if r["record_type"] == "agentsight.process_nodes" and pid(r) == pid(subject)]
                if not matches:
                    continue
                duplicate = copy.deepcopy(matches[0])
                duplicate["source"]["row"] = "synthetic-overlap-" + str(duplicate["source"]["row"])
                modified.append(duplicate)
            actual = next(d for d in align(modified, manifest["run_id"])[0]
                          if d["source_ref"] == source_ref and d["relation"] == "tool_calls_process")
            perturbations.append({"source_ref": source_ref, "treatment": treatment,
                                  "expected_status": expected, "actual_status": actual["status"],
                                  "passed": actual["status"] == expected,
                                  "evidence_status": "SYNTHETIC_PERTURBATION_OF_REAL_RECORD"})
    return {
        "run_id": manifest["run_id"], "input_audit": frozen,
        "raw_consistency": {"checked": len(checks), "passed": sum(c["passed"] for c in checks), "checks": checks,
                            "scope": "PID and bounded timestamp consistency in raw SQLite; no independent labels"},
        "perturbations": {"total": len(perturbations), "passed": sum(p["passed"] for p in perturbations),
                          "cases": perturbations, "scope": "Software robustness; not real failures or model runs"},
        "by_relation": summary["by_relation"], "precision": None, "recall": None,
        "independent_review_status": "AUTHOR_INPUT_NEEDED",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Refusing to overwrite existing audit")
    report = audit(args.manifest, args.evidence)
    write_json(args.output, report)
    print(json.dumps({"run_id": report["run_id"],
                      "raw_consistency": {k: report["raw_consistency"][k] for k in ("checked", "passed")},
                      "perturbations": {k: report["perturbations"][k] for k in ("total", "passed")}}))
    return 0 if all(c["passed"] for c in report["raw_consistency"]["checks"] + report["perturbations"]["cases"]) else 2


if __name__ == "__main__":
    raise SystemExit(main())
