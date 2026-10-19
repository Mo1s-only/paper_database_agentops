from __future__ import annotations

import re
from typing import Any

from . import SCHEMA_VERSION
from .common import TRUTH_FIELDS


HEX64 = re.compile(r"^[0-9a-f]{64}$")
TRUTH_STATES = {"direct", "derived", "partial", "abstain"}
EVIDENCE_FIELDS = {"source_path", "json_pointer", "record_sha256", "support", "method"}


def _validate_evidence(item: Any, path: str, errors: list[str]) -> None:
    if not isinstance(item, dict):
        errors.append(f"{path}: evidence must be an object")
        return
    missing = EVIDENCE_FIELDS - set(item)
    if missing:
        errors.append(f"{path}: missing evidence fields {sorted(missing)}")
    if item.get("support") not in {"direct", "derived"}:
        errors.append(f"{path}: invalid support")
    if not HEX64.fullmatch(str(item.get("record_sha256", ""))):
        errors.append(f"{path}: record_sha256 must be 64 lowercase hex characters")


def _validate_evidence_list(value: Any, path: str, errors: list[str], *, nonempty: bool) -> None:
    if not isinstance(value, list):
        errors.append(f"{path}: evidence must be a list")
        return
    if nonempty and not value:
        errors.append(f"{path}: evidence must not be empty")
    for index, item in enumerate(value):
        _validate_evidence(item, f"{path}/{index}", errors)


def validate_record(record: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(record, dict):
        return ["record must be an object"]
    required = {"schema_version", "dataset", "run", "agents", "steps", "relations", "truth", "provenance", "quality"}
    missing = required - set(record)
    if missing:
        errors.append(f"record missing fields {sorted(missing)}")
        return errors
    if record.get("schema_version") != SCHEMA_VERSION:
        errors.append("schema_version mismatch")

    run = record.get("run")
    if not isinstance(run, dict) or not run.get("run_id"):
        errors.append("run.run_id is required")
    dataset = record.get("dataset")
    if not isinstance(dataset, dict) or not all(dataset.get(key) for key in ("name", "version", "split")):
        errors.append("dataset name/version/split are required")

    agents = record.get("agents")
    steps = record.get("steps")
    relations = record.get("relations")
    if not isinstance(agents, list) or not isinstance(steps, list) or not isinstance(relations, list):
        errors.append("agents, steps and relations must be arrays")
        return errors

    agent_ids: set[str] = set()
    for index, agent in enumerate(agents):
        if not isinstance(agent, dict) or not agent.get("agent_id"):
            errors.append(f"agents/{index}: agent_id is required")
            continue
        if agent["agent_id"] in agent_ids:
            errors.append(f"agents/{index}: duplicate agent_id {agent['agent_id']}")
        agent_ids.add(agent["agent_id"])
        _validate_evidence_list(agent.get("evidence"), f"agents/{index}/evidence", errors, nonempty=True)

    step_ids: set[str] = set()
    for index, step in enumerate(steps):
        if not isinstance(step, dict) or not step.get("step_id"):
            errors.append(f"steps/{index}: step_id is required")
            continue
        if step["step_id"] in step_ids:
            errors.append(f"steps/{index}: duplicate step_id {step['step_id']}")
        step_ids.add(step["step_id"])
        if not isinstance(step.get("sequence"), int) or step["sequence"] < 0:
            errors.append(f"steps/{index}: sequence must be a non-negative integer")
        if not HEX64.fullmatch(str(step.get("content_sha256", ""))):
            errors.append(f"steps/{index}: invalid content_sha256")
        _validate_evidence_list(step.get("evidence"), f"steps/{index}/evidence", errors, nonempty=True)

    relation_ids: set[str] = set()
    for index, relation in enumerate(relations):
        if not isinstance(relation, dict) or not relation.get("relation_id"):
            errors.append(f"relations/{index}: relation_id is required")
            continue
        if relation["relation_id"] in relation_ids:
            errors.append(f"relations/{index}: duplicate relation_id {relation['relation_id']}")
        relation_ids.add(relation["relation_id"])
        if relation.get("source_step_id") not in step_ids or relation.get("target_step_id") not in step_ids:
            errors.append(f"relations/{index}: source/target must reference existing steps")
        _validate_evidence_list(relation.get("evidence"), f"relations/{index}/evidence", errors, nonempty=True)

    truth = record.get("truth")
    if not isinstance(truth, dict):
        errors.append("truth must be an object")
    else:
        for field in TRUTH_FIELDS:
            label = truth.get(field)
            if not isinstance(label, dict):
                errors.append(f"truth/{field}: missing label object")
                continue
            state = label.get("state")
            values = label.get("values")
            evidence_items = label.get("evidence")
            if state not in TRUTH_STATES:
                errors.append(f"truth/{field}: invalid state {state!r}")
            if not isinstance(values, list):
                errors.append(f"truth/{field}: values must be a list")
            elif state == "abstain" and values:
                errors.append(f"truth/{field}: abstain must have empty values")
            elif state != "abstain" and not values:
                errors.append(f"truth/{field}: non-abstain must have values")
            _validate_evidence_list(
                evidence_items,
                f"truth/{field}/evidence",
                errors,
                nonempty=state != "abstain",
            )
            if state == "abstain" and evidence_items:
                errors.append(f"truth/{field}: abstain must have empty evidence")
            if not label.get("reason"):
                errors.append(f"truth/{field}: reason is required")

    provenance = record.get("provenance")
    if not isinstance(provenance, dict) or not provenance.get("adapter"):
        errors.append("provenance.adapter is required")
    else:
        sources = provenance.get("source_records")
        if not isinstance(sources, list) or not sources:
            errors.append("provenance.source_records must not be empty")
        else:
            for index, source in enumerate(sources):
                if not isinstance(source, dict) or not source.get("source_path") or not HEX64.fullmatch(str(source.get("sha256", ""))):
                    errors.append(f"provenance/source_records/{index}: invalid source record")
    quality = record.get("quality")
    if not isinstance(quality, dict) or not isinstance(quality.get("warnings"), list):
        errors.append("quality.warnings must be a list")
    return errors

