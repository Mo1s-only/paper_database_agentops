#!/usr/bin/env bash
# Observe a real Claude process with AgentSight's WSL2 attach-mode workaround.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT="${1:-${ROOT}/results/agentsight-attach-$(date -u +%Y%m%dT%H%M%SZ)}"
AGENTSIGHT_TEST_ROOT="${AGENTSIGHT_TEST_ROOT:-/mnt/c/Users/mobao/Desktop/agentsight/test}"
AGENTSIGHT_BIN="${AGENTSIGHT_BIN:-agentsight}"
mkdir -p "${OUT}/workspace"

die() { echo "ERROR: $*" >&2; exit 1; }
[ "$(uname -s)" = "Linux" ] || die "run this script inside WSL2"
[ "$(id -u)" = "0" ] || die "run as root so AgentSight can attach its probes"

if [ ! -d /sys/kernel/tracing/events/sched ]; then
    mount -t tracefs tracefs /sys/kernel/tracing 2>/dev/null || true
fi
[ -d /sys/kernel/tracing/events/sched/sched_process_exec ] || die "sched_process_exec tracepoint missing"
[ -f "${AGENTSIGHT_TEST_ROOT}/.env" ] || die "missing ${AGENTSIGHT_TEST_ROOT}/.env"
set -a
. "${AGENTSIGHT_TEST_ROOT}/.env"
set +a
export ANTHROPIC_BASE_URL="${ANTHROPIC_BASE_URL:-https://api.deepseek.com/anthropic}"
export ANTHROPIC_MODEL="${ANTHROPIC_MODEL:-deepseek-v4-pro}"
export ANTHROPIC_SMALL_FAST_MODEL="${ANTHROPIC_SMALL_FAST_MODEL:-deepseek-flash}"
export CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1
command -v claude >/dev/null 2>&1 || die "claude not found"
command -v "${AGENTSIGHT_BIN}" >/dev/null 2>&1 || die "agentsight not found"

DB="${OUT}/session.db"
PROMPT="Use Bash exactly once to run: python3 '${ROOT}/fake_inventory.py' alpha . Do not edit files or call any other tool. Read the JSON result, compare it with the task requirement that alpha must have available=1, and report whether the requirement is satisfied."

cat > "${OUT}/probe-truth.json" <<'JSON'
{
  "schema_version": "agentops-ground-truth-v0.1",
  "fault_type": "silent_tool_error",
  "task_requirement": {"item": "alpha", "available": 1},
  "tool_observation": {"status": "ok", "item": "alpha", "available": 0},
  "responsible_agent": "claude",
  "responsible_step": "claude.bash_tool_call",
  "truth_source": "fixed local fake_inventory.py and this probe manifest"
}
JSON

cd "${OUT}/workspace" || die "cannot enter workspace"
echo "attach-mode output=${OUT}"
echo "starting monitor..."
timeout 300 "${AGENTSIGHT_BIN}" record -c claude --db "${DB}" --no-server > "${OUT}/record.log" 2>&1 &
RPID=$!
sleep "${ATTACH_DELAY:-2}"
timeout 300 "${AGENTSIGHT_BIN}" debug process > "${OUT}/raw-stream.log" 2>&1 &
SPID=$!
sleep 1

claude -p "${PROMPT}" \
    --output-format json \
    --model "${ANTHROPIC_MODEL}" \
    --allowedTools Bash Read Write > "${OUT}/claude-run.log" 2>&1
AGENT_RC=$?
echo "${AGENT_RC}" > "${OUT}/agent-exit.txt"
sleep 3
kill -INT "${RPID}" 2>/dev/null; wait "${RPID}" 2>/dev/null
kill "${SPID}" 2>/dev/null; wait "${SPID}" 2>/dev/null

for sub in summary token prompts audit; do
    "${AGENTSIGHT_BIN}" report "${sub}" --db "${DB}" > "${OUT}/report-${sub}.txt" 2>&1
done
if [ -f "${AGENTSIGHT_TEST_ROOT}/inspect-db.py" ]; then
    python3 "${AGENTSIGHT_TEST_ROOT}/inspect-db.py" "${DB}" > "${OUT}/db-rows.txt" 2>&1
fi
cat > "${OUT}/run-info.txt" <<EOF
mode=attach-by-command
agent_exit=${AGENT_RC}
model=${ANTHROPIC_MODEL}
endpoint=${ANTHROPIC_BASE_URL}
EOF
echo "agent_exit=${AGENT_RC}"
grep -E 'Recorded|API calls|tokens|execs|files|network' "${OUT}/record.log" | tail -5 || true
exit "${AGENT_RC}"
