#!/usr/bin/env python3
"""Deterministic local tool used only by the AgentSight attach-mode probe."""

from __future__ import annotations

import argparse
import json


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("item")
    args = parser.parse_args()
    # Deliberately valid-looking but wrong result. The expected value is kept
    # in the probe truth file, not in this tool's output.
    print(json.dumps({"status": "ok", "item": args.item, "available": 0}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
