#!/usr/bin/env python3
"""Versioned application events with strict lifecycle validation; no model/API calls."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import time
import uuid

VERSION = "agentops-application-event-v0.1"
KINDS = {"session.start", "step.start", "tool.start", "tool.end", "step.end", "session.end"}
KEYS = {"schema_version", "evidence_kind", "run_id", "event_id", "session_id", "agent_id",
        "event_type", "sequence", "timestamp_ms", "step_id", "tool_call_id", "process", "clock"}


def integer(value, minimum=0):
    return isinstance(value, int) and not isinstance(value, bool) and value >= minimum


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def validate_event(event: dict) -> None:
    if not isinstance(event, dict) or set(event) != KEYS:
        raise ValueError("Application event requires exactly the v0.1 fields; extra fields are not allowed")
    if event["schema_version"] != VERSION or event["event_type"] not in KINDS:
        raise ValueError("Unknown event schema or type")
    if event["evidence_kind"] not in {"runtime_observed", "synthetic_fixture"}:
        raise ValueError("Unknown evidence kind")
    for name in ("run_id", "event_id", "session_id", "agent_id"):
        if not nonempty(event[name]):
            raise ValueError(f"Missing identifier: {name}")
    if not integer(event["sequence"]) or not integer(event["timestamp_ms"]):
        raise ValueError("Sequence and timestamp must be nonnegative integers")
    process, clock = event["process"], event["clock"]
    if not isinstance(process, dict) or set(process) != {"host_id", "boot_id", "pid_namespace", "pid", "start_ms"}:
        raise ValueError("Missing scoped process identity")
    if not all(nonempty(process[k]) for k in ("host_id", "boot_id", "pid_namespace")):
        raise ValueError("Process identity requires host, boot and PID namespace")
    if not integer(process["pid"], 1) or not integer(process["start_ms"]):
        raise ValueError("Invalid process PID or start timestamp")
    if not isinstance(clock, dict) or set(clock) != {"domain", "uncertainty_ms"}:
        raise ValueError("Missing clock declaration")
    if not nonempty(clock["domain"]) or not integer(clock["uncertainty_ms"]):
        raise ValueError("Clock uncertainty must be bounded and nonnegative")
    if event["timestamp_ms"] + clock["uncertainty_ms"] < process["start_ms"]:
        raise ValueError("Event precedes process start")
    kind = event["event_type"]
    if kind.startswith("session."):
        if event["step_id"] is not None or event["tool_call_id"] is not None:
            raise ValueError("Session event cannot claim a step or tool")
    elif not nonempty(event["step_id"]):
        raise ValueError("Step identity required")
    if kind.startswith("tool."):
        if not nonempty(event["tool_call_id"]):
            raise ValueError("Tool event requires the actual shared tool_call_id")
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
        run_ids.add(event["run_id"])
        evidence_kinds.add(event["evidence_kind"])
        if len(run_ids) > 1 or len(evidence_kinds) > 1:
            raise ValueError("Mixed runs or synthetic/runtime evidence in one stream")
        sid, kind = event["session_id"], event["event_type"]
        identity = (event["agent_id"], event["process"], event["clock"])
        if sid not in sessions:
            if kind != "session.start" or event["sequence"] != 0:
                raise ValueError("Session must begin with session.start at sequence 0")
            sessions[sid] = {"identity": copy.deepcopy(identity), "sequence": -1, "timestamp": -1,
                             "closed": False, "steps": {}, "tools": {}}
        state = sessions[sid]
        if state["closed"] or identity != state["identity"]:
            raise ValueError("Closed session or changed identity/process/clock")
        if event["sequence"] != state["sequence"] + 1 or event["timestamp_ms"] < state["timestamp"]:
            raise ValueError("Non-contiguous sequence or backwards timestamp")
        state["sequence"], state["timestamp"] = event["sequence"], event["timestamp_ms"]
        step, tool = event["step_id"], event["tool_call_id"]
        if kind == "session.start" and state["sequence"] != 0:
            raise ValueError("Duplicate session.start")
        if kind == "step.start":
            if step in state["steps"]:
                raise ValueError("Step ID reused in a session")
            state["steps"][step] = "open"
        elif kind in {"tool.start", "tool.end", "step.end"}:
            if state["steps"].get(step) != "open":
                raise ValueError("Event references a non-open step")
            if kind == "tool.start":
                if tool in state["tools"]:
                    raise ValueError("Tool ID reused; retries require a new actual call ID")
                state["tools"][tool] = (step, "open")
            elif kind == "tool.end":
                if state["tools"].get(tool) != (step, "open"):
                    raise ValueError("Tool end has no matching open tool")
                state["tools"][tool] = (step, "closed")
            else:
                if any(s == step and status == "open" for s, status in state["tools"].values()):
                    raise ValueError("Step ended with open tool")
                state["steps"][step] = "closed"
        elif kind == "session.end":
            if any(value == "open" for value in state["steps"].values()):
                raise ValueError("Session ended with open steps")
            state["closed"] = True
    complete = all(s["closed"] for s in sessions.values())
    if require_closed and not complete:
        raise ValueError("Incomplete session stream")
    return {"run_id": next(iter(run_ids)), "evidence_kind": next(iter(evidence_kinds)),
            "event_count": len(events), "session_count": len(sessions), "all_sessions_closed": complete}


def read_events(path: Path) -> tuple[list[dict], dict]:
    events = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            raise ValueError("Blank application event line")
        events.append(json.loads(line))
    return events, validate_stream(events)


class EventWriter:
    """One writer per application session. Caller supplies measured process identity and real tool IDs.

    Does not generate fake provider IDs or infer steps from final summaries. Call finish()
    to check closure. Partial logs survive exceptions and are rejected by strict readers.
    """
    def __init__(self, path: Path, run_id: str, session_id: str, agent_id: str,
                 process: dict, clock: dict, evidence_kind="runtime_observed"):
        self.path, self.events = path, []
        self.base = {"schema_version": VERSION, "run_id": run_id, "session_id": session_id,
                     "agent_id": agent_id, "process": copy.deepcopy(process), "clock": copy.deepcopy(clock),
                     "evidence_kind": evidence_kind}
        self.stream = path.open("x", encoding="utf-8")

    def emit(self, event_type: str, step_id=None, tool_call_id=None, timestamp_ms=None):
        event = {**self.base, "event_id": str(uuid.uuid4()), "event_type": event_type,
                 "sequence": len(self.events), "timestamp_ms": time.time_ns() // 1000000 if timestamp_ms is None else timestamp_ms,
                 "step_id": step_id, "tool_call_id": tool_call_id}
        validate_stream(self.events + [event], require_closed=False)
        self.stream.write(json.dumps(event, ensure_ascii=False) + "\n")
        self.stream.flush()
        self.events.append(copy.deepcopy(event))
        return copy.deepcopy(event)

    def finish(self):
        try:
            return validate_stream(self.events)
        finally:
            self.stream.close()

    def close(self):
        self.stream.close()
