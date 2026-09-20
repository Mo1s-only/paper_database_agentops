#!/usr/bin/env bash
# AgentSight end-to-end test: observe Claude Code (DeepSeek-backed) with eBPF.
#
# Must run inside WSL2 — eBPF needs a Linux kernel and can only see processes
# in the same kernel, so the observed agent runs here too.
#
# NOTE ON THE ATTACH-MODE WORKAROUND
# ----------------------------------
# `agentsight record -- <cmd>` (launch mode) captures nothing under WSL2: the
# target and its children exec normally, but zero events reach the DB. The
# same probes work fine when attached to an already-running process, and
# `agentsight debug process` streams the events without trouble — so the
# kernel side is healthy and the loss is in launch-mode session attribution.
#
# This script therefore launches the agent itself and attaches by PID, which
# is the path that actually produces data here.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE="${ROOT}/workspace"
OUT="${ROOT}/out"
DB="${OUT}/session.db"
AGENTSIGHT="${AGENTSIGHT_BIN:-agentsight}"
ATTACH_DELAY="${ATTACH_DELAY:-2}"

die() { echo "ERROR: $*" >&2; exit 1; }

# --- 0. must be Linux ------------------------------------------------------
[ "$(uname -s)" = "Linux" ] || die "this test needs Linux; run it inside WSL2, not Git Bash"

# --- 1. tracefs ------------------------------------------------------------
# WSL2 does not mount tracefs by default. Without it libbpf cannot resolve
# tracepoint perf event IDs and every probe fails to attach with -ENOENT.
# Mounts do not survive a WSL restart, so do this every run.
if [ ! -d /sys/kernel/tracing/events/sched ]; then
    mount -t tracefs tracefs /sys/kernel/tracing 2>/dev/null || true
fi
mount -t debugfs debugfs /sys/kernel/debug 2>/dev/null || true

[ -d /sys/kernel/tracing/events/sched/sched_process_exec ] \
    || die "sched_process_exec tracepoint missing — eBPF probes cannot attach"

# --- 2. privileges ---------------------------------------------------------
# record() elevates only its own probes; the agent itself stays unprivileged.
[ "$(id -u)" = "0" ] || die "agentsight record needs root for eBPF probes (WSL2 default user is root)"

# --- 3. credentials --------------------------------------------------------
if [ -f "${ROOT}/.env" ]; then
    set -a; . "${ROOT}/.env"; set +a
fi
[ -n "${ANTHROPIC_AUTH_TOKEN:-}" ] || die "ANTHROPIC_AUTH_TOKEN unset — cp .env.example .env and add your key"

export ANTHROPIC_BASE_URL="${ANTHROPIC_BASE_URL:-https://api.deepseek.com/anthropic}"
export ANTHROPIC_MODEL="${ANTHROPIC_MODEL:-deepseek-v4-pro}"
export ANTHROPIC_SMALL_FAST_MODEL="${ANTHROPIC_SMALL_FAST_MODEL:-deepseek-flash}"
# keep Claude Code from making telemetry calls that would muddy the capture
export CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1

command -v claude >/dev/null 2>&1 || die "claude not found — run ./setup.sh first"
command -v "${AGENTSIGHT}" >/dev/null 2>&1 || die "agentsight not found — run ./setup.sh first"

# --- 4. fresh state --------------------------------------------------------
rm -rf "${OUT}" "${WORKSPACE}"
mkdir -p "${OUT}" "${WORKSPACE}"

PROMPT='Create a file named hello.txt in the current directory containing exactly the line: AgentSight test. Then read it back and report its contents.'

echo "=== AgentSight e2e test ==============================================="
echo "kernel     : $(uname -r)"
echo "agentsight : $("${AGENTSIGHT}" --version)"
echo "claude     : $(claude --version 2>&1 | head -1)"
echo "endpoint   : ${ANTHROPIC_BASE_URL}"
echo "model      : ${ANTHROPIC_MODEL}"
echo "mode       : attach by PID"
echo "========================================================================="

# --- 5. start monitoring, then launch the agent ----------------------------
# Tools are pinned to Write and Read only — no Bash, no network. That is
# enough to produce a real tool call and a real file effect for AgentSight to
# observe, without handing the agent a general-purpose shell.
cd "${WORKSPACE}" || die "cannot cd to workspace"

# Comm-match mode (the documented `sudo agentsight record -c claude` flow).
# Start it before the agent so the agent's exec and every syscall after it
# fall inside the capture window.
echo "starting monitor (record -c claude)..."
timeout 300 agentsight record -c claude --db "${DB}" --no-server \
    > "${OUT}/record.log" 2>&1 &
RPID=$!
sleep "${ATTACH_DELAY}"

# Raw unfiltered event stream alongside it. record's DB path has been lossy
# under WSL2, and this stream is the ground truth for what the probes saw.
timeout 300 agentsight debug process > "${OUT}/raw-stream.log" 2>&1 &
SPID=$!
sleep 1

echo "launching agent..."
claude -p "${PROMPT}" \
    --output-format json \
    --model "${ANTHROPIC_MODEL}" \
    --allowedTools "Write" "Read" > "${OUT}/claude-run.log" 2>&1
AGENT_RC=$?
echo "agent exit: ${AGENT_RC}"

sleep 3
kill -INT "${RPID}" 2>/dev/null; wait "${RPID}" 2>/dev/null
kill "${SPID}" 2>/dev/null; wait "${SPID}" 2>/dev/null

echo "--- record log ---"
grep -vE '^\s*$' "${OUT}/record.log" | tail -8
echo "--- raw stream: $(grep -c '"event"' "${OUT}/raw-stream.log" 2>/dev/null) events ---"

# --- 6. reports ------------------------------------------------------------
for sub in summary token prompts audit; do
    echo "--- report ${sub} ---"
    "${AGENTSIGHT}" report --db "${DB}" "${sub}" 2>&1 | tee "${OUT}/report-${sub}.txt"
done
"${AGENTSIGHT}" report list 2>&1 | tee "${OUT}/report-list.txt"

# --- 7. raw DB truth -------------------------------------------------------
echo "--- db row counts (ground truth, independent of report formatting) ---"
python3 "${ROOT}/inspect-db.py" "${DB}" 2>&1 | tee "${OUT}/db-rows.txt"

echo
echo "artifacts in ${OUT}:"
ls -la "${OUT}"
echo
echo "now run: ./verify.sh"
