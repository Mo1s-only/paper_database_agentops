#!/usr/bin/env bash
set -euo pipefail

repo_root="${1:?repository root is required}"
results="$repo_root/lab/experiment/experiment_20261013_13/results"
agentsight="$repo_root/lab/agentsight/source/thesis_adapter/collector/target/release/agentsight"
marker="agentops-direct-pid-20261013-13"

mountpoint -q /sys/kernel/tracing || mount -t tracefs tracefs /sys/kernel/tracing
test -r /sys/kernel/tracing/events/sched/sched_process_exec/id

"$agentsight" debug process -- -c echo \
  > "$results/agentsight-process.jsonl" \
  2> "$results/agentsight-process.stderr" &
observer=$!
cleanup() {
  kill -INT "$observer" 2>/dev/null || true
  wait "$observer" 2>/dev/null || true
}
trap cleanup EXIT
sleep 2

python3 - "$marker" "$results/target-process.json" <<'PY'
import json
import subprocess
import sys
import time

marker, output = sys.argv[1:]
process = subprocess.Popen(
    ["/bin/echo", marker], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
)
value = {
    "marker": marker,
    "userspace_pid": process.pid,
    "started_monotonic_ns": time.monotonic_ns(),
}
value["exit_code"] = process.wait(timeout=5)
value["ended_monotonic_ns"] = time.monotonic_ns()
with open(output, "w", encoding="utf-8") as stream:
    json.dump(value, stream, indent=2)
    stream.write("\n")
PY

sleep 2
cleanup
trap - EXIT
