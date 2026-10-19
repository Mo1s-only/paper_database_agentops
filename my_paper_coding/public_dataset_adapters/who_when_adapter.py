from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from .common import base_record, evidence, sha256_bytes, sha256_text, stable_id, truth_label


DATASET_VERSION = "f4d2b6d"


def adapt_file(path: Path, dataset_root: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    digest = sha256_bytes(raw)
    obj = json.loads(raw)
    rel = path.relative_to(dataset_root).as_posix()
    source = {"source_path": rel, "sha256": digest}
    split = path.parent.name
    question_id = str(obj.get("question_ID") or path.stem)
    run_id = f"whowhen:{split}:{path.stem}"
    record = base_record(
        dataset_name="Who&When",
        dataset_version=DATASET_VERSION,
        split=split,
        source_records=[source],
        run_id=run_id,
        session_id=question_id,
        task_id=question_id,
    )

    history = obj.get("history") if isinstance(obj.get("history"), list) else []
    agent_names: list[str] = []
    for entry in history:
        if isinstance(entry, dict) and entry.get("name"):
            agent_names.append(str(entry["name"]))
    if isinstance(obj.get("system_prompt"), dict):
        agent_names.extend(str(name) for name in obj["system_prompt"].keys())
    if obj.get("mistake_agent"):
        agent_names.append(str(obj["mistake_agent"]))

    for name in dict.fromkeys(agent_names):
        pointer = "/mistake_agent" if name == str(obj.get("mistake_agent")) else "/history"
        record["agents"].append(
            {
                "agent_id": name,
                "role": None,
                "evidence": [
                    evidence(rel, pointer, digest, support="direct", method="dataset agent name")
                ],
            }
        )

    for index, entry in enumerate(history):
        if not isinstance(entry, dict):
            entry = {"content": entry}
        content = entry.get("content", "")
        name = str(entry["name"]) if entry.get("name") else None
        role = str(entry.get("role") or "unknown")
        event_type = "message"
        lowered_name = (name or "").lower()
        if "terminal" in lowered_name or "tool" in lowered_name:
            event_type = "tool.result"
        record["steps"].append(
            {
                "step_id": f"history:{index}",
                "sequence": index,
                "agent_id": name,
                "event_type": event_type,
                "timestamp": None,
                "role": role,
                "content_sha256": sha256_text(str(content)),
                "evidence": [
                    evidence(
                        rel,
                        f"/history/{index}",
                        digest,
                        support="direct",
                        method="history array entry",
                    )
                ],
            }
        )

    for index in range(max(0, len(history) - 1)):
        record["relations"].append(
            {
                "relation_id": stable_id("relation", run_id, index, index + 1, "temporal"),
                "source_step_id": f"history:{index}",
                "target_step_id": f"history:{index + 1}",
                "relation_type": "temporal",
                "evidence": [
                    evidence(
                        rel,
                        "/history",
                        digest,
                        support="derived",
                        method="adjacent array order; no causal claim",
                    )
                ],
            }
        )
    record["quality"]["relation_opportunities"] = max(0, len(history) - 1)
    record["quality"]["relations_reconstructed"] = len(record["relations"])

    mistake_agent = str(obj.get("mistake_agent") or "").strip()
    mistake_step_raw = str(obj.get("mistake_step") or "").strip()
    agent_ev = evidence(
        rel,
        "/mistake_agent",
        digest,
        support="direct",
        method="Who&When failure-responsible agent annotation",
    )
    if mistake_agent:
        record["truth"]["responsibility_agents"] = truth_label(
            "direct",
            [mistake_agent],
            reason="Who&When directly annotates the failure-responsible agent.",
            evidence_items=[agent_ev],
        )

    try:
        mistake_index = int(mistake_step_raw)
    except ValueError:
        mistake_index = -1
    if 0 <= mistake_index < len(history):
        step_id = f"history:{mistake_index}"
        step_ev = evidence(
            rel,
            "/mistake_step",
            digest,
            support="direct",
            method="Who&When zero-based decisive error step annotation",
        )
        record["truth"]["responsibility_steps"] = truth_label(
            "direct",
            [step_id],
            reason="Who&When directly annotates the decisive error step index.",
            evidence_items=[step_ev],
        )
        record["truth"]["root_cause_nodes"] = truth_label(
            "derived",
            [step_id],
            reason="The decisive error step is represented as the corresponding graph node without changing its semantics.",
            evidence_items=[
                evidence(
                    rel,
                    "/mistake_step",
                    digest,
                    support="derived",
                    method="lossless decisive-step to node-id mapping",
                )
            ],
        )
    else:
        record["quality"]["warnings"].append(
            f"mistake_step {mistake_step_raw!r} does not index history of length {len(history)}"
        )

    record["truth"]["propagation_edges"]["reason"] = (
        "Who&When does not directly annotate error-propagation edges."
    )
    record["truth"]["causal_paths"]["reason"] = (
        "Who&When does not directly annotate a complete causal path."
    )
    record["quality"].update(
        {
            "history_steps": len(history),
            "task_failed": not bool(obj.get("is_correct")),
            "mistake_reason_available": bool(obj.get("mistake_reason")),
        }
    )
    return record


def iter_records(dataset_root: Path) -> Iterable[dict[str, Any]]:
    for path in sorted(dataset_root.rglob("*.json"), key=lambda value: value.as_posix()):
        yield adapt_file(path, dataset_root)
