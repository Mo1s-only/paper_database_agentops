#!/usr/bin/env bash
# Minimal two-agent capture using AgentSight's WSL2 attach-mode workaround.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT="${1:-${ROOT}/results/agentsight-two-agent-$(date -u +%Y%m%dT%H%M%SZ)}"
AGENTSIGHT_TEST_ROOT="${AGENTSIGHT_TEST_ROOT:-/mnt/c/Users/mobao/Desktop/agentsight/test}"
AGENTSIGHT_BIN="${AGENTSIGHT_BIN:-agentsight}"
WORKSPACE="${OUT}/workspace"
mkdir -p "${WORKSPACE}"

die() { echo "ERROR: $*" >&2; exit 1; }
[ "$(uname -s)" = "Linux" ] || die "run inside WSL2"
[ "$(id -u)" = "0" ] || die "run as root"
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
getent hosts api.deepseek.com >/dev/null 2>&1 || die "api.deepseek.com DNS lookup failed; stop before any API call"

DB="${OUT}/session.db"
cat > "${OUT}/ground_truth.json" <<'JSON'
{
  "schema_version": "agentops-ground-truth-v0.1",
  "fault_type": "silent_tool_error",
  "responsible_agent": "agent_b",
  "responsible_step": "agent_b.bash_tool_call",
  "responsible_edge": {"from": "agent_b.bash_tool_call", "to": "agent_b.decision"},
  "task_requirement": {"item": "alpha", "available": 1},
  "tool_observation": {"item": "alpha", "available": 0},
  "truth_source": "fixed prompts, local fake_inventory.py, and this manifest"
}
JSON

PROMPT_A="You are Agent A, the planner. Use Write exactly once to create ${WORKSPACE}/route.json containing exactly this JSON object: {\"item\":\"alpha\",\"required_available\":1}. Do not call any other tool. Then report that the route was created."
PROMPT_B="You are Agent B, the executor. First use Read exactly once to read ${WORKSPACE}/route.json. Then use Bash exactly once to run: python3 '${ROOT}/fake_inventory.py' alpha. Then use Write exactly once to create ${WORKSPACE}/decision.json containing JSON with item alpha, required_available 1, observed_available 0, satisfied false. Do not call any other tool."

cd "${WORKSPACE}" || die "cannot enter workspace"
timeout 360 "${AGENTSIGHT_BIN}" record -c claude --db "${DB}" --no-server > "${OUT}/record.log" 2>&1 &
RPID=$!
sleep "${ATTACH_DELAY:-2}"
if ! kill -0 "${RPID}" 2>/dev/null; then
    echo "ERROR: AgentSight record exited before the first API call; inspect ${OUT}/record.log" >&2
    wait "${RPID}" 2>/dev/null || true
    exit 2
fi
timeout 360 "${AGENTSIGHT_BIN}" debug process > "${OUT}/raw-stream.log" 2>&1 &
SPID=$!
sleep 1
if ! kill -0 "${SPID}" 2>/dev/null; then
    echo "ERROR: AgentSight process probe exited before the first API call; inspect ${OUT}/raw-stream.log" >&2
    kill "${RPID}" 2>/dev/null || true
    wait "${RPID}" 2>/dev/null || true
    exit 2
fi

timeout "${CLAUDE_TIMEOUT_SEC:-90}" claude -p "${PROMPT_A}" --output-format json --model "${ANTHROPIC_MODEL}" --allowedTools Write > "${OUT}/claude-agent-a.log" 2>&1
RC_A=$?
if [ "${RC_A}" -eq 0 ]; then
    timeout "${CLAUDE_TIMEOUT_SEC:-90}" claude -p "${PROMPT_B}" --output-format json --model "${ANTHROPIC_MODEL}" --allowedTools Read Bash Write > "${OUT}/claude-agent-b.log" 2>&1
    RC_B=$?
else
    printf '%s\n' "skipped_after_agent_a_failure" > "${OUT}/claude-agent-b.log"
    RC_B=125
fi
printf '%s\n' "${RC_A}" > "${OUT}/agent-a-exit.txt"
printf '%s\n' "${RC_B}" > "${OUT}/agent-b-exit.txt"
sleep 3
kill -INT "${RPID}" 2>/dev/null; wait "${RPID}" 2>/dev/null
kill "${SPID}" 2>/dev/null; wait "${SPID}" 2>/dev/null

if [ ! -s "${DB}" ]; then
    echo "ERROR: AgentSight did not create a non-empty session database; inspect ${OUT}/record.log" >&2
    exit 2
fi

for sub in summary token prompts audit; do
    "${AGENTSIGHT_BIN}" report "${sub}" --db "${DB}" > "${OUT}/report-${sub}.txt" 2>&1
done
if [ -f "${AGENTSIGHT_TEST_ROOT}/inspect-db.py" ]; then
    python3 "${AGENTSIGHT_TEST_ROOT}/inspect-db.py" "${DB}" > "${OUT}/db-rows.txt" 2>&1
fi
cat > "${OUT}/run-info.txt" <<EOF
mode=attach-by-command
agent_a_exit=${RC_A}
agent_b_exit=${RC_B}
model=${ANTHROPIC_MODEL}
endpoint=${ANTHROPIC_BASE_URL}
EOF
echo "agent_a_exit=${RC_A} agent_b_exit=${RC_B}"
grep -E 'Recorded|API calls|tokens|execs|files|network' "${OUT}/record.log" | tail -5 || true
if [ "${RC_A}" -ne 0 ] || [ "${RC_B}" -ne 0 ]; then exit 1; fi
exit 0
