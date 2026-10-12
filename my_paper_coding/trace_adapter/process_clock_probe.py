#!/usr/bin/env python3
"""Emit one process and three-clock observation as a JSON object."""
import json
import os
from pathlib import Path
import time


def status_values(pid: int):
    values = {}
    for line in Path(f"/proc/{pid}/status").read_text(encoding="utf-8").splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            if key in {"Pid", "PPid", "NSpid"}:
                values[key.lower()] = [int(item) for item in value.split()]
    return values


def main():
    pid = os.getpid()
    stat = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8")
    fields = stat[stat.rfind(")") + 2:].split()
    realtime_before = time.time_ns()
    monotonic = time.monotonic_ns()
    boottime = time.clock_gettime_ns(time.CLOCK_BOOTTIME)
    realtime_after = time.time_ns()
    result = {"schema_version": "agentops-process-clock-probe-v0.1", **status_values(pid),
              "pid_namespace_link": os.readlink(f"/proc/{pid}/ns/pid"),
              "proc_start_ticks": int(fields[19]), "clock_ticks_per_second": os.sysconf("SC_CLK_TCK"),
              "realtime_interval_ns": [realtime_before, realtime_after],
              "monotonic_ns": monotonic, "boottime_ns": boottime,
              "realtime_uncertainty_ns": (realtime_after - realtime_before + 1) // 2}
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
