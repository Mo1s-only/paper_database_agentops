from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from .common import base_record, evidence, sha256_bytes, sha256_text, stable_id, truth_label


DATASET_VERSION = "iclr2026-aiwild-camera-ready/323fc63"


def adapt_file(path: Path, dataset_root: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    digest = sha256_bytes(raw)
    outer = json.loads(raw)
    graph = json.loads(outer["trace_json"])
    rel = path.relative_to(dataset_root).as_posix()
    scenario_id = str(outer.get("scenario_id") or path.stem.replace("_trace", ""))
    run_id = str(graph.get("run_id") or f"agenttrace:{scenario_id}")
    domain = scenario_id.split("_", 1)[0]
    record = base_record(
        dataset_name="AgentTrace",
        dataset_version=DATASET_VERSION,
        split="synthetic-canonical-traces",
        source_records=[{"source_path": rel, "sha256": digest}],
        run_id=run_id,
        session_id=run_id,
        task_id=scenario_id,
    )

    nodes = graph.get("nodes") if isinstance(graph.get("nodes"), list) else []
    edges = graph.get("edges") if isinstance(graph.get("edges"), list) else []
    node_by_id: dict[str, dict[str, Any]] = {}
    agent_pointers: dict[str, str] = {}
    for index, node in enumerate(nodes):
        if not isinstance(node, dict):
            continue
        node_id = str(node.get("id") or stable_id("missing-node", scenario_id, index))
        node_by_id[node_id] = node
        agent_id = str(node.get("agent_id") or "").strip() or None
        if agent_id:
            agent_pointers.setdefault(agent_id, f"/trace_json#/nodes/{index}/agent_id")
        data = node.get("data") if isinstance(node.get("data"), dict) else {}
        record["steps"].append(
            {
                "step_id": node_id,
                "sequence": index,
                "agent_id": agent_id,
                "event_type": str(node.get("type") or data.get("action") or "node"),
                "timestamp": str(node["timestamp"]) if node.get("timestamp") is not None else None,
                "native_step": data.get("step"),
                "action": data.get("action"),
                "content_sha256": sha256_text(
                    json.dumps(data, ensure_ascii=False, sort_keys=True, default=str)
                ),
                "evidence": [
                    evidence(
                        rel,
                        "/trace_json",
                        digest,
                        support="direct",
                        method=f"embedded graph node id={node_id}",
                    )
                ],
            }
        )

    for agent_id, pointer in agent_pointers.items():
        record["agents"].append(
            {
                "agent_id": agent_id,
                "role": None,
                "evidence": [
                    evidence(
                        rel,
                        "/trace_json",
                        digest,
                        support="direct",
                        method=f"embedded node agent_id={agent_id} at {pointer}",
                    )
                ],
            }
        )

    edge_by_pair: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for index, edge in enumerate(edges):
        if not isinstance(edge, dict):
            continue
        source = str(edge.get("source_id") or "")
        target = str(edge.get("target_id") or "")
        if source not in node_by_id or target not in node_by_id:
            record["quality"]["warnings"].append(
                f"edge {edge.get('id', index)} references a missing node"
            )
            continue
        relation_id = str(edge.get("id") or stable_id("relation", scenario_id, source, target, index))
        converted = {
            "relation_id": relation_id,
            "source_step_id": source,
            "target_step_id": target,
            "relation_type": str(edge.get("type") or "graph_edge"),
            "confidence": edge.get("confidence"),
            "evidence": [
                evidence(
                    rel,
                    "/trace_json",
                    digest,
                    support="direct",
                    method=f"embedded graph edge id={relation_id}",
                )
            ],
        }
        record["relations"].append(converted)
        edge_by_pair.setdefault((source, target), []).append(converted)
    record["quality"]["relation_opportunities"] = len(edges)
    record["quality"]["relations_reconstructed"] = len(record["relations"])

    root_id = str(outer.get("root_cause_node_id") or "").strip()
    if root_id and root_id in node_by_id:
        root_ev = evidence(
            rel,
            "/root_cause_node_id",
            digest,
            support="direct",
            method="AgentTrace root_cause_node_id annotation",
        )
        record["truth"]["root_cause_nodes"] = truth_label(
            "direct",
            [root_id],
            reason="AgentTrace directly annotates the root-cause node ID.",
            evidence_items=[root_ev],
        )
        root = node_by_id[root_id]
        agent_id = str(root.get("agent_id") or "").strip()
        if agent_id:
            record["truth"]["responsibility_agents"] = truth_label(
                "derived",
                [agent_id],
                reason="The responsible Agent is obtained by a unique lookup of the annotated root-cause node.",
                evidence_items=[
                    evidence(
                        rel,
                        "/root_cause_node_id",
                        digest,
                        support="derived",
                        method=f"root node {root_id} -> node.agent_id",
                    )
                ],
            )
        record["truth"]["responsibility_steps"] = truth_label(
            "derived",
            [root_id],
            reason="The annotated root-cause node is represented as the responsible graph step.",
            evidence_items=[
                evidence(
                    rel,
                    "/root_cause_node_id",
                    digest,
                    support="derived",
                    method=f"root node {root_id} -> unified step_id",
                )
            ],
        )
    elif root_id:
        record["quality"]["warnings"].append("root_cause_node_id did not match a graph node")

    path_ids = [str(value) for value in (outer.get("causal_path") or [])]
    if path_ids and all(node_id in node_by_id for node_id in path_ids):
        path_ev = evidence(
            rel,
            "/causal_path",
            digest,
            support="direct",
            method="AgentTrace ordered causal_path annotation",
        )
        record["truth"]["causal_paths"] = truth_label(
            "direct",
            [{"node_ids": path_ids}],
            reason="AgentTrace directly annotates the ordered root-to-error path.",
            evidence_items=[path_ev],
        )
        path_edges: list[dict[str, str]] = []
        missing_pairs: list[tuple[str, str]] = []
        for source, target in zip(path_ids, path_ids[1:]):
            candidates = edge_by_pair.get((source, target), [])
            if not candidates:
                missing_pairs.append((source, target))
                continue
            selected = candidates[0]
            path_edges.append(
                {
                    "relation_id": selected["relation_id"],
                    "source_step_id": source,
                    "target_step_id": target,
                }
            )
        if path_edges:
            state = "derived" if not missing_pairs else "partial"
            record["truth"]["propagation_edges"] = truth_label(
                state,
                path_edges,
                reason=(
                    "Consecutive annotated path nodes were mapped to explicit graph edges."
                    if not missing_pairs
                    else "Only a subset of consecutive causal-path node pairs matched explicit graph edges."
                ),
                evidence_items=[
                    evidence(
                        rel,
                        "/causal_path",
                        digest,
                        support="derived",
                        method="consecutive causal_path node pairs -> explicit edge lookup",
                    )
                ],
            )
        if missing_pairs:
            record["quality"]["warnings"].append(
                f"{len(missing_pairs)} causal path pairs lacked an explicit edge"
            )
    elif path_ids:
        record["quality"]["warnings"].append("causal_path referenced a missing graph node")

    record["quality"].update(
        {
            "domain": domain,
            "nodes": len(nodes),
            "source_edges": len(edges),
            "root_node_present": bool(root_id and root_id in node_by_id),
        }
    )
    return record


def iter_records(dataset_root: Path) -> Iterable[dict[str, Any]]:
    trace_root = dataset_root / "traces"
    for path in sorted(trace_root.glob("*_trace.json"), key=lambda value: value.as_posix()):
        yield adapt_file(path, dataset_root)
