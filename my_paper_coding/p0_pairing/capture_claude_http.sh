#!/usr/bin/env bash
set -euo pipefail

ENV_FILE="${P0_ENV_FILE:?set P0_ENV_FILE to the existing local credential file}"
OUT_DIR="${P0_OUT_DIR:?set P0_OUT_DIR to a dedicated output directory}"
AGENTSIGHT_BIN="${AGENTSIGHT_BIN:-agentsight}"
CLAUDE_BIN="${CLAUDE_BIN:-claude}"
CLAUDE_SSL_BINARY="${CLAUDE_SSL_BINARY:-/usr/local/lib/node_modules/@anthropic-ai/claude-code/bin/claude.exe}"

mkdir -p "${OUT_DIR}"
set -a
. "${ENV_FILE}"
set +a

export ANTHROPIC_BASE_URL="${ANTHROPIC_BASE_URL:-https://api.deepseek.com/anthropic}"
export ANTHROPIC_MODEL="${ANTHROPIC_MODEL:-deepseek-v4-pro}"
export CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1

marker="P0_$(date -u +%Y%m%dT%H%M%SZ)_$RANDOM"
printf '%s\n' "${marker}" > "${OUT_DIR}/marker.txt"

timeout 120 "${AGENTSIGHT_BIN}" debug ssl \
  --binary-path "${CLAUDE_SSL_BINARY}" \
  --http-parser \
  --http-raw-data \
  > "${OUT_DIR}/ssl-http.jsonl" \
  2> "${OUT_DIR}/ssl-http.err" &
capture_pid=$!

cleanup() {
  kill -INT "${capture_pid}" 2>/dev/null || true
  wait "${capture_pid}" 2>/dev/null || true
}
trap cleanup EXIT

sleep 3
set +e
timeout 180 "${CLAUDE_BIN}" -p "Reply with exactly: ${marker}" \
  --output-format json \
  --model "${ANTHROPIC_MODEL}" \
  --allowedTools "Read" \
  > "${OUT_DIR}/claude.json" \
  2> "${OUT_DIR}/claude.err"
agent_rc=$?
set -e
printf '%s\n' "${agent_rc}" > "${OUT_DIR}/agent-exit.txt"
sleep 3
cleanup
trap - EXIT

python3 - "${OUT_DIR}/ssl-http.jsonl" "${OUT_DIR}/capture-summary.json" <<'PY'
import json
import sys
from collections import Counter

source, target = sys.argv[1:]
summary = {
    "json_lines": 0,
    "sources": Counter(),
    "message_types": Counter(),
    "pid_tid": Counter(),
    "directions": Counter(),
}
with open(source, "r", encoding="utf-8", errors="replace") as handle:
    for line in handle:
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        summary["json_lines"] += 1
        summary["sources"][str(event.get("source"))] += 1
        data = event.get("data") or {}
        summary["message_types"][str(data.get("message_type"))] += 1
        summary["directions"][str(data.get("direction"))] += 1
        summary["pid_tid"][f'{event.get("pid")}:{data.get("tid")}'] += 1
for key in ("sources", "message_types", "pid_tid", "directions"):
    summary[key] = dict(summary[key])
with open(target, "w", encoding="utf-8") as handle:
    json.dump(summary, handle, ensure_ascii=False, indent=2)
print(json.dumps(summary, ensure_ascii=False, indent=2))
PY
