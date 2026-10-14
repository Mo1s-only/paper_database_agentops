#!/usr/bin/env python3
"""Focused integrity checks for the static dashboard package."""
from __future__ import annotations

import json
from pathlib import Path


SITE = Path(__file__).resolve().parents[1]
DIST = SITE / "dist"
data = json.loads((DIST / "data.json").read_text(encoding="utf-8"))

assert data["headline"]["directPid"] == {
    "initial": 1791, "collector": 34, "userspace": 34, "status": "accepted"
}
assert data["headline"]["testsPassed"] == 101
assert data["headline"]["fieldCompleteness"] == 1.0
assert data["quality"]["invalidRejected"] == data["quality"]["invalidCases"] == 8
assert data["headline"]["budget"]["status"] == "BLOCKED"
assert data["evidence"]["readiness"]["causal_attribution"] is False
assert len(data["experiments"]) == 7

html = (DIST / "index.html").read_text(encoding="utf-8")
for asset in ("styles.css", "app.js"):
    assert asset in html and (DIST / asset).exists(), asset
assert "data.json" in (DIST / "app.js").read_text(encoding="utf-8")
print("dashboard validation passed")
