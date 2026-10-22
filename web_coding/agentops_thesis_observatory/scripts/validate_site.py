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
assert data["headline"]["budget"]["status"] in {"BLOCKED", "PARTIAL"}
assert data["headline"]["budget"]["plannedBatchCny"] == 1.8
assert data["headline"]["budget"]["batchCapCny"] == 2.0
assert data["headline"]["budget"]["ledgerReconciled"] is False
assert data["evidence"]["readiness"]["causal_attribution"] is False
assert len(data["experiments"]) == 9
catalog = {row["id"]: row for row in data["datasetCatalog"]}
assert len(catalog) == len(data["datasetCatalog"]) == 7
assert {row["id"] for row in data["datasetModes"]} == {
    "cross_layer_live", "semantic_diagnosis", "adapter_compatibility", "synthetic_stress"
}
assert catalog["error-propagation-v1"]["apiRequired"] is True
assert catalog["error-propagation-v1"]["pairedSystemObservations"] == "on_new_run"
assert catalog["agentrx-tau12"]["recordCount"] == 1
assert catalog["agentrx-tau12"]["pairedSystemObservations"] == "none"
assert {name: catalog[name]["recordCount"] for name in ("who-when", "trail", "agenttrace")} == {
    "who-when": 184, "trail": 148, "agenttrace": 550
}
assert catalog["alignment-stress-1000"]["recordCount"] == 1000
assert all(not catalog[name]["apiRequired"] for name in ("who-when", "trail", "agenttrace", "alignment-stress-1000"))
assert all(dataset_id in catalog for row in data["experiments"] for dataset_id in row.get("datasetIds", []))
planned = next(row for row in data["experiments"] if row["id"] == "experiment_20261019_18")
if planned["datasetEvidence"] == "planned_only":
    assert planned["networkCalls"] == 0
else:
    assert planned["datasetEvidence"] == "runtime_observed_partial"
    assert planned["status"] == "partial"
    assert planned["networkCalls"] == "3 CLI 会话"
    assert data["headline"]["budget"]["status"] == "PARTIAL"
    assert 0 < data["headline"]["budget"]["reportedIncrementalCnyAtRate"] < 2.0
capture = data["captureIntegrity"]
assert capture["aggregate"]["nativeToolCalls"] == 15
assert capture["aggregate"]["capturedToolCalls"] == 12
assert capture["aggregate"]["missingIdsInSqlite"] == 0
assert capture["reproducedFromRawRuns"] is False
assert {x["missingStep"] for x in capture["scenarios"]} == {"agent_a.bash_1", "agent_a.write_1"}
assert "observer-lifecycle.jsonl" in capture["futureInstrumentation"]
scale = data["datasetExpansion"]
assert scale["syntheticFixtureCount"] == 1000
assert scale["syntheticFixtureEvidenceKind"] == "synthetic_fixture"
assert scale["syntheticFixtureApiCalls"] == 0
assert scale["syntheticFixtureProductionAlignerExercised"] is False
assert scale["plannedAdditionalRuns"] == 9
assert scale["perExperimentCapCny"] == 2.0
assert scale["perExperimentPlannedUpperCny"] <= scale["perExperimentCapCny"]
assert scale["plannedBatchUpperCny"] == 17.28
assert scale["networkCallsMade"] == 0

html = (DIST / "index.html").read_text(encoding="utf-8")
for asset in ("styles.css", "app.js"):
    assert asset in html and (DIST / asset).exists(), asset
assert "data.json" in (DIST / "app.js").read_text(encoding="utf-8")
assert 'id="experimentConfigForm"' in html
assert 'id="datasetSelect"' in html and 'name="datasetSelect" required' in html
assert 'id="datasetDetails"' in html
assert 'id="continueAgentRx"' in html
assert "dataset_id:dataset.id" in (DIST / "app.js").read_text(encoding="utf-8")
print("dashboard validation passed")
