#!/usr/bin/env python3
"""Read a label-isolated public-dataset replay input and emit structural counts only."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def summarize(value: dict) -> dict:
    dataset = value.get("dataset")
    if dataset == "AgentTrace":
        graph = value.get("graph", {})
        count = len(graph.get("nodes", [])) + len(graph.get("edges", []))
    elif dataset == "WhoAndWhen":
        count = 1 + len(value.get("history", []))
    elif dataset == "TRAIL":
        count = len(value.get("spans", []))
    else:
        raise ValueError("Unexpected or missing public dataset family")
    return {"dataset": dataset, "sample_id": value.get("sample_id"), "item_count": count}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    args = parser.parse_args()
    value = json.loads(args.input.read_text(encoding="utf-8"))
    print(json.dumps(summarize(value), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
