#!/usr/bin/env python3
"""Application event protocol v0.2 with explicit PID and clock evidence."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import uuid

from process_identity import DIRECT_METHOD

VERSION = "agentops-application-event-v0.2"
KINDS = {"session.start", "step.start", "tool.start", "tool.end", "step.end", "session.end"}
KEYS = {"schema_version", "evidence_kind", "run_id", "event_id", "session_id", "agent_id",
        "event_type", "sequence", "step_id", "tool_call_id", "process", "clock"}
PROCESS_KEYS = {"host_id", "boot_id", "local_pid", "local_pid_namespace", "observer_pid",
                "observer_pid_namespace", "mapping_status", "mapping_method", "mapping_evidence",
                "start_realtime_interval_ns", "observer_start_epoch_ms"}
CLOCK_KEYS = {"application_realtime_ns", "application_realtime_interval_ns",
              "application_monotonic_ns", "application_boottime_ns", "application_uncertainty_ns",
              "observer_raw_boot_ns", "observer_epoch_ms", "observer_boot_epoch_ns",
              "observer_anchor_uncertainty_ns", "conversion", "correction_ns"}


def integer(value, minimum=0):
    return isinstance(value, int) and not isinstance(value, bool) and value >= minimum


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def nullable_integer(value, minimum=0):
    return value is None or integer(value, minimum)


def validate_event(event: dict) -> None:
    if not isinstance(event, dict) or set(event) != KEYS:
        raise ValueError("Application event requires exactly the v0.2 fields")
    if event["schema_version"] != VERSION or event["event_type"] not in KINDS:
        raise ValueError("Unknown event schema or type")
    if event["evidence_kind"] not in {"runtime_observed", "synthetic_fixture"}:
        raise ValueError("Unknown evidence kind")
    for name in ("run_id", "event_id", "session_id", "agent_id"):
        if not nonempty(event[name]):
            raise ValueError(f"Missing identifier: {name}")
    if not integer(event["sequence"]):
        raise ValueError("Sequence must be a nonnegative integer")

    process = event["process"]
    if not isinstance(process, dict) or set(process) != PROCESS_KEYS:
        raise ValueError("Missing exact v0.2 process declaration")
    if not all(nonempty(process[name]) for name in
               ("host_id", "boot_id", "local_pid_namespace")):
        raise ValueError("Process scope requires host, boot and local PID namespace")
    if not integer(process["local_pid"], 1):
        raise ValueError("Invalid local PID")
    interval = process["start_realtime_interval_ns"]
    if not (isinstance(interval, list) and len(interval) == 2 and
            all(integer(value) for value in interval) and interval[0] <= interval[1]):
        raise ValueError("Invalid process start interval")
    if process["mapping_status"] not in {"accepted", "inferred", "abstain"}:
        raise ValueError("Unknown PID mapping status")
    observer_pair = (process["observer_pid"], process["observer_pid_namespace"])
    if process["mapping_status"] == "abstain":
        if observer_pair != (None, None) or process["mapping_method"] is not None:
            raise ValueError("Abstained PID mapping cannot claim observer identity")
    else:
        if not integer(process["observer_pid"], 1) or not nonempty(process["observer_pid_namespace"]):
            raise ValueError("Mapped process requires observer PID and namespace")
        if not nonempty(process["mapping_method"]):
            raise ValueError("Mapped process requires a method")
    evidence = process["mapping_evidence"]
    if not isinstance(evidence, list) or not all(nonempty(item) for item in evidence):
        raise ValueError("PID mapping evidence must be a string list")
    if not evidence or len(evidence) != len(set(evidence)):
        raise ValueError("PID mapping decision requires unique evidence")
    if process["mapping_status"] == "accepted":
        if process["mapping_method"] != DIRECT_METHOD or not any(
                item.startswith("proc.status.NSpid=") for item in evidence):
            raise ValueError("Accepted PID mapping requires direct NSpid evidence")
    if not nullable_integer(process["observer_start_epoch_ms"]):
        raise ValueError("Invalid observer process start time")

    clock = event["clock"]
    if not isinstance(clock, dict) or set(clock) != CLOCK_KEYS:
        raise ValueError("Missing exact v0.2 clock declaration")
    for name in ("application_realtime_ns", "application_monotonic_ns",
                 "application_boottime_ns", "application_uncertainty_ns"):
        if not integer(clock[name]):
            raise ValueError(f"Invalid clock field: {name}")
    realtime_interval = clock["application_realtime_interval_ns"]
    if not (isinstance(realtime_interval, list) and len(realtime_interval) == 2 and
            all(integer(value) for value in realtime_interval) and
            realtime_interval[0] <= clock["application_realtime_ns"] <= realtime_interval[1]):
        raise ValueError("Application realtime midpoint must lie inside its interval")
    if clock["application_uncertainty_ns"] < (realtime_interval[1] - realtime_interval[0] + 1) // 2:
        raise ValueError("Application uncertainty understates the measured interval")
    observer_values = [clock[name] for name in ("observer_raw_boot_ns", "observer_epoch_ms",
                                                 "observer_boot_epoch_ns",
                                                 "observer_anchor_uncertainty_ns")]
    if any(value is None for value in observer_values):
        if any(value is not None for value in observer_values) or clock["conversion"] is not None:
            raise ValueError("Observer clock fields must be present or absent together")
        if clock["correction_ns"] is not None:
            raise ValueError("Clock correction requires observer evidence")
    else:
        if not all(integer(value) for value in observer_values):
            raise ValueError("Invalid observer clock evidence")
        if clock["conversion"] != "boot_epoch_ns_plus_bpf_ktime_ns":
            raise ValueError("Unknown observer clock conversion")
        expected_ms = (clock["observer_boot_epoch_ns"] + clock["observer_raw_boot_ns"]) // 1_000_000
        if clock["observer_epoch_ms"] != expected_ms:
            raise ValueError("Observer epoch time does not match raw boot time and anchor")
        if not integer(clock["correction_ns"]):
            raise ValueError("Correction must be explicit; use zero for the native conversion")

    kind = event["event_type"]
    if kind.startswith("session."):
        if event["step_id"] is not None or event["tool_call_id"] is not None:
            raise ValueError("Session event cannot claim a step or tool")
    elif not nonempty(event["step_id"]):
        raise ValueError("Step identity required")
    if kind.startswith("tool."):
        if not nonempty(event["tool_call_id"]):
            raise ValueError("Tool event requires the shared tool_call_id")
    elif event["tool_call_id"] is not None:
        raise ValueError("Non-tool event cannot claim a tool_call_id")


def validate_stream(events: list[dict], require_closed=True) -> dict:
    if not events:
        raise ValueError("Empty application event stream")
    sessions, seen, run_ids, evidence_kinds = {}, set(), set(), set()
    for event in events:
        validate_event(event)
        if event["event_id"] in seen:
            raise ValueError("Duplicate application event_id")
        seen.add(event["event_id"])
        run_ids.add(event["run_id"]); evidence_kinds.add(event["evidence_kind"])
        if len(run_ids) > 1 or len(evidence_kinds) > 1:
            raise ValueError("Mixed runs or evidence kinds")
        sid, kind = event["session_id"], event["event_type"]
        identity = (event["agent_id"], event["process"])
        if sid not in sessions:
            if kind != "session.start" or event["sequence"] != 0:
                raise ValueError("Session must begin with session.start at sequence 0")
            sessions[sid] = {"identity": copy.deepcopy(identity), "sequence": -1, "realtime": -1,
                             "closed": False, "steps": {}, "tools": {}}
        state = sessions[sid]
        if state["closed"] or identity != state["identity"]:
            raise ValueError("Closed session or changed process identity")
        current = event["clock"]["application_realtime_ns"]
        if event["sequence"] != state["sequence"] + 1 or current < state["realtime"]:
            raise ValueError("Non-contiguous sequence or backwards application clock")
        state["sequence"], state["realtime"] = event["sequence"], current
        step, tool = event["step_id"], event["tool_call_id"]
        if kind == "session.start" and state["sequence"] != 0:
            raise ValueError("Duplicate session.start")
        if kind == "step.start":
            if step in state["steps"]:
                raise ValueError("Step ID reused")
            state["steps"][step] = "open"
        elif kind in {"tool.start", "tool.end", "step.end"}:
            if state["steps"].get(step) != "open":
                raise ValueError("Event references a non-open step")
            if kind == "tool.start":
                if tool in state["tools"]:
                    raise ValueError("Tool ID reused")
                state["tools"][tool] = (step, "open")
            elif kind == "tool.end":
                if state["tools"].get(tool) != (step, "open"):
                    raise ValueError("Tool end has no matching start")
                state["tools"][tool] = (step, "closed")
            else:
                if any(s == step and status == "open" for s, status in state["tools"].values()):
                    raise ValueError("Step ended with open tool")
                state["steps"][step] = "closed"
        elif kind == "session.end":
            if any(value == "open" for value in state["steps"].values()):
                raise ValueError("Session ended with open steps")
            state["closed"] = True
    complete = all(state["closed"] for state in sessions.values())
    if require_closed and not complete:
        raise ValueError("Incomplete session stream")
    return {"run_id": next(iter(run_ids)), "evidence_kind": next(iter(evidence_kinds)),
            "event_count": len(events), "session_count": len(sessions),
            "all_sessions_closed": complete}


def read_events(path: Path) -> tuple[list[dict], dict]:
    events = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            raise ValueError("Blank application event line")
        events.append(json.loads(line))
    return events, validate_stream(events)


def write_events(path: Path, events: list[dict]) -> dict:
    summary = validate_stream(events)
    with path.open("x", encoding="utf-8") as stream:
        for event in events:
            stream.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
    return summary


def stable_event_id(event_value: dict) -> str:
    """Derive an event ID from stable protocol identity rather than run-time randomness."""
    identity = "\x1f".join(str(event_value.get(name) or "") for name in (
        "schema_version", "run_id", "session_id", "agent_id", "event_type", "sequence",
        "step_id", "tool_call_id",
    ))
    return str(uuid.uuid5(uuid.NAMESPACE_URL, identity))


def canonicalize_events(events: list[dict]) -> list[dict]:
    """Return a byte-stable replay form while preserving the original evidence fields."""
    validate_stream(events)
    canonical = copy.deepcopy(events)
    for value in canonical:
        value["event_id"] = stable_event_id(value)
    validate_stream(canonical)
    return canonical


def event(base: dict, event_type: str, sequence: int, clock: dict,
          step_id=None, tool_call_id=None) -> dict:
    value = {**copy.deepcopy(base), "event_id": str(uuid.uuid4()), "event_type": event_type,
             "sequence": sequence, "clock": copy.deepcopy(clock), "step_id": step_id,
             "tool_call_id": tool_call_id}
    value["event_id"] = stable_event_id(value)
    validate_event(value)
    return value
