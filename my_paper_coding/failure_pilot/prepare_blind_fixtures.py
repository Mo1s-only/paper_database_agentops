#!/usr/bin/env python3
"""Materialize sanitized synthetic fixtures for blind pipeline checks only."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from run_fault_matrix import FAULTS, build_run


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--repetitions", type=int, default=3)
    args = parser.parse_args()
    if args.repetitions < 1:
        parser.error("--repetitions must be at least 1")

    # Exclusive creation makes an accidental overwrite impossible.
    args.out_dir.mkdir(parents=True, exist_ok=False)
    index = 0
    for fault in FAULTS:
        for repetition in range(1, args.repetitions + 1):
            index += 1
            run_id = f"blind-{index:04d}"
            trace, truth = build_run(fault, repetition)
            run_dir = args.out_dir / run_id
            run_dir.mkdir()
            clean_trace = []
            for original in trace:
                item = dict(original)
                item["run_id"] = run_id
                item.pop("attributes", None)
                clean_trace.append(item)
            clean_truth = dict(truth)
            clean_truth["run_id"] = run_id
            clean_truth["responsible_action_event_id"] = next(
                item["event_id"] for item in clean_trace
                if item["step_id"] == clean_truth["responsible_step"]
            )
            with (run_dir / "trace.jsonl").open("x", encoding="utf-8", newline="\n") as handle:
                for item in clean_trace:
                    handle.write(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n")
            with (run_dir / "ground_truth.json").open("x", encoding="utf-8", newline="\n") as handle:
                json.dump(clean_truth, handle, ensure_ascii=False, indent=2, sort_keys=True)
                handle.write("\n")
    print(f"Prepared {index} sanitized synthetic fixtures at {args.out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
