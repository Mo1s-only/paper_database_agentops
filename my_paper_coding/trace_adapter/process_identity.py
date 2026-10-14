#!/usr/bin/env python3
"""Evidence-bounded PID namespace mapping decisions for pre-attribution traces."""
from __future__ import annotations


DIRECT_METHOD = "proc_status_nspid"
BPF_DIRECT_METHOD = "bpf_get_ns_current_pid_tgid"
DIRECT_METHODS = {DIRECT_METHOD, BPF_DIRECT_METHOD}
INDIRECT_METHOD = "session+comm+launch_interval+shared_tool_call_id"


def direct_mapping_evidence_valid(method: str | None, evidence: list[str]) -> bool:
    """Accept only methods whose evidence encodes both PID namespace views."""
    prefixes = {
        DIRECT_METHOD: "proc.status.NSpid=",
        BPF_DIRECT_METHOD: "bpf.pidns.tgid=",
    }
    prefix = prefixes.get(method)
    if prefix is None:
        return False
    for item in evidence:
        if not item.startswith(prefix):
            continue
        values = item[len(prefix):].split(",")
        if (method == DIRECT_METHOD and len(values) < 2) or (
                method == BPF_DIRECT_METHOD and len(values) != 2):
            continue
        try:
            if all(int(value) > 0 for value in values):
                return True
        except ValueError:
            continue
    return False


def positive_integer(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def direct_vector_match(local_pid: int, candidate: dict) -> bool:
    vector = candidate.get("nspid_vector")
    if not (isinstance(vector, list) and len(vector) >= 2 and
            all(positive_integer(value) for value in vector)):
        return False
    if vector[0] != candidate.get("observer_pid") or vector[-1] != local_pid:
        return False
    return True


def decide_pid_mapping(local_pid: int, local_pid_namespace: str | None,
                       candidates: list[dict], indirect_evidence: list[str] | None = None) -> dict:
    """Return accepted only for unique NSpid truth, inferred for unique indirect evidence."""
    if not positive_integer(local_pid):
        raise ValueError("local_pid must be a positive integer")
    if local_pid_namespace is not None and not str(local_pid_namespace).strip():
        raise ValueError("local_pid_namespace must be nonempty when present")
    pid_direct = [candidate for candidate in candidates if direct_vector_match(local_pid, candidate)]
    if local_pid_namespace is None and pid_direct:
        return {
            "mapping_status": "abstain", "mapping_method": None,
            "mapping_evidence": ["local_pid_namespace_missing"],
            "observer_pid": None, "observer_pid_namespace": None,
            "reason": "ambiguous_local_pid_across_namespaces" if len(pid_direct) > 1
                      else "local_pid_namespace_missing",
            "candidate_count": len(pid_direct),
        }
    direct = [candidate for candidate in pid_direct
              if candidate.get("process_pid_namespace") == local_pid_namespace]
    if len(direct) == 1:
        candidate = direct[0]
        vector = candidate["nspid_vector"]
        return {
            "mapping_status": "accepted",
            "mapping_method": DIRECT_METHOD,
            "mapping_evidence": [f"proc.status.NSpid={','.join(map(str, vector))}"],
            "observer_pid": candidate["observer_pid"],
            "observer_pid_namespace": candidate.get("observer_pid_namespace"),
            "reason": "unique_direct_nspid_mapping",
            "candidate_count": len(direct),
        }
    if len(direct) > 1:
        return {
            "mapping_status": "abstain", "mapping_method": None,
            "mapping_evidence": ["ambiguous_direct_nspid_candidates"],
            "observer_pid": None, "observer_pid_namespace": None,
            "reason": "ambiguous_local_pid_across_namespaces", "candidate_count": len(direct),
        }

    indirect_evidence = [value for value in (indirect_evidence or [])
                         if isinstance(value, str) and value.strip()]
    indirect = [candidate for candidate in candidates if candidate.get("indirect_match") is True]
    if len(indirect) == 1 and indirect_evidence:
        candidate = indirect[0]
        return {
            "mapping_status": "inferred", "mapping_method": INDIRECT_METHOD,
            "mapping_evidence": indirect_evidence,
            "observer_pid": candidate["observer_pid"],
            "observer_pid_namespace": candidate.get("observer_pid_namespace"),
            "reason": "unique_supported_indirect_mapping", "candidate_count": 1,
        }
    return {
        "mapping_status": "abstain", "mapping_method": None,
        "mapping_evidence": ["no_unique_supported_mapping"],
        "observer_pid": None, "observer_pid_namespace": None,
        "reason": "no_unique_supported_mapping", "candidate_count": len(indirect),
    }
