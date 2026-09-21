#!/usr/bin/env bash
# Probe-capability checks for running AgentSight under WSL2.
#
# Run this when run-test.sh produces an empty session: it separates "the eBPF
# layer is broken" from "this particular record mode is broken".
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
D="${ROOT}/out-diag"
mkdir -p "${D}"
mount -t tracefs tracefs /sys/kernel/tracing 2>/dev/null || true
mount -t debugfs debugfs /sys/kernel/debug 2>/dev/null || true

echo "=== 1. kernel and tracefs ==="
uname -r
mount | grep -E 'tracefs|debugfs' || echo "  tracefs NOT mounted (probes will fail with -ENOENT)"
echo "  sched tracepoints: $(ls /sys/kernel/tracing/events/sched 2>/dev/null | wc -l)"
echo "  bpf config: $(zcat /proc/config.gz 2>/dev/null | grep -c '^CONFIG_BPF=y')"

echo
echo "=== 2. does the kernel's own ftrace see exec events? ==="
# If this shows nothing, the problem is below AgentSight and nothing else matters.
TP=/sys/kernel/tracing/events/sched/sched_process_exec
echo 1 > "${TP}/enable" 2>/dev/null
: > /sys/kernel/tracing/trace 2>/dev/null
/bin/true; /bin/true
sleep 1
echo 0 > "${TP}/enable" 2>/dev/null
n=$(grep -c 'sched_process_exec' /sys/kernel/tracing/trace 2>/dev/null)
if [ "${n:-0}" -gt 0 ]; then echo "  OK: ftrace captured ${n} exec events"
else echo "  FAIL: ftrace captured nothing"; fi

echo
echo "=== 3. does AgentSight's raw stream see exec events? ==="
timeout 20 agentsight debug process > "${D}/stream.log" 2>&1 &
SP=$!
sleep 5
/bin/true; /usr/bin/env true >/dev/null 2>&1; sleep 1
kill ${SP} 2>/dev/null; wait ${SP} 2>/dev/null
n=$(grep -c '"event":"EXEC"' "${D}/stream.log" 2>/dev/null)
if [ "${n:-0}" -gt 0 ]; then echo "  OK: raw stream captured ${n} EXEC events -> eBPF works"
else echo "  FAIL: raw stream captured nothing -> eBPF does not work here"; fi

echo
echo "=== 4. which record mode persists to the DB? ==="
probe() { # probe <label> <db> <args...>
    local label="$1" db="$2"; shift 2
    rm -f "${db}"*
    timeout 40 agentsight record "$@" --db "${db}" --no-server >/dev/null 2>&1 &
    local p=$!
    sleep 4
    /bin/true; /usr/bin/env true >/dev/null 2>&1; bash -c 'true'
    sleep 3
    kill -INT ${p} 2>/dev/null; wait ${p} 2>/dev/null
    local rows
    rows=$(python3 "${ROOT}/inspect-db.py" "${db}" 2>/dev/null | tail -1)
    printf '  %-34s %s\n' "${label}" "${rows:-<no db>}"
}

probe "launch mode: -- <cmd>"    "${D}/launch.db" -- bash -c 'true'
probe "attach mode: -c bash"     "${D}/attach.db" -c bash

echo
echo "Expected: launch mode persists ~0 rows, attach mode persists real rows."
echo "run-test.sh uses attach mode for exactly this reason."
