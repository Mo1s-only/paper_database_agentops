#!/usr/bin/env bash
# Assert AgentSight actually captured what it claims to.
#
# Checks are tiered on purpose: the file effect and the LLM/TLS capture come
# from different probes, and it is worth knowing which tier failed.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT="${ROOT}/out"
WORKSPACE="${ROOT}/workspace"

pass=0; fail=0

ok()   { printf '  PASS  [%s] %s\n' "$1" "$2"; pass=$((pass + 1)); }
bad()  { printf '  FAIL  [%s] %s\n        %s\n' "$1" "$2" "$3"; fail=$((fail + 1)); }

# check <tier> <name> <file> <extended-regex>
check() {
    local tier="$1" name="$2" file="$3" pat="$4"
    [ -f "$file" ] || { bad "$tier" "$name" "missing file: ${file#${ROOT}/}"; return; }
    if grep -qiE "$pat" "$file"; then ok "$tier" "$name"
    else bad "$tier" "$name" "no match for /${pat}/ in ${file#${ROOT}/}"; fi
}

# nonzero <tier> <name> <db-rows-file> <table>
nonzero() {
    local tier="$1" name="$2" file="$3" table="$4"
    [ -f "$file" ] || { bad "$tier" "$name" "missing ${file#${ROOT}/}"; return; }
    local n
    n=$(awk -v t="$table" '$1==t {print $2}' "$file")
    if [ -z "$n" ]; then bad "$tier" "$name" "table '${table}' not in ${file#${ROOT}/}"
    elif [ "$n" -gt 0 ]; then ok "$tier" "$name (${table}=${n})"
    else bad "$tier" "$name" "${table} is 0 — probe attached but nothing persisted"; fi
}

echo "=== AgentSight capture verification ==================================="

echo
echo "-- tier 1: the agent really ran, and had a real effect on the filesystem"
check "run"     "claude produced a result"      "${OUT}/claude-run.log"   '"result"'
check "effect"  "hello.txt written by agent"    "${WORKSPACE}/hello.txt"  'AgentSight test'

echo
echo "-- tier 2: eBPF process / exec / file capture"
nonzero "ebpf"  "process tree captured"         "${OUT}/db-rows.txt" 'process_nodes'
nonzero "ebpf"  "audit trail captured"          "${OUT}/db-rows.txt" 'audit_events'
check   "ebpf"  "agent exec attributed to claude" "${OUT}/report-audit.txt" 'claude.*exec|exec.*claude'
check   "ebpf"  "record reports non-zero execs" "${OUT}/record.log"       '[1-9][0-9]* execs'

echo
echo "-- tier 3: TLS / LLM capture (model, prompt, tokens)"
nonzero "tls"   "LLM calls captured"            "${OUT}/db-rows.txt" 'llm_calls'
nonzero "tls"   "token usage captured"          "${OUT}/db-rows.txt" 'token_usage'
check   "tls"   "model name captured"           "${OUT}/report-token.txt" 'deepseek'
check   "tls"   "non-zero token counts"         "${OUT}/report-token.txt" '[1-9][0-9]{3,}'
check   "tls"   "prompt text captured"          "${OUT}/report-prompts.txt" 'hello\.txt'

echo
echo "-- tier 4: tool calls and network"
nonzero "tools" "tool calls captured"           "${OUT}/db-rows.txt" 'tool_calls'
nonzero "net"   "network endpoints captured"    "${OUT}/db-rows.txt" 'network_targets'

echo
echo "======================================================================="
printf 'passed %d, failed %d\n' "$pass" "$fail"

if [ "$fail" -gt 0 ]; then
    echo
    echo "Inspect the raw artifacts in test/out/ to see how far capture got."
    exit 1
fi

echo
echo "AgentSight observed Claude Code end to end: the agent's exec, its file"
echo "writes, its Write/Read tool calls, and the DeepSeek model calls with"
echo "prompt text and token counts — all without an SDK or a proxy."
