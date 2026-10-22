#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
if [[ $# -lt 1 || $# -gt 3 ]]; then
  echo "Usage: $0 <new-output-directory> [cli-session-soft-budget-usd] [--ignore-cumulative-budget]" >&2
  exit 2
fi
if [[ ! -t 0 ]]; then
  echo "Run interactively so the DeepSeek key can be entered without echo." >&2
  exit 2
fi

if [[ -z "${DEEPSEEK_API_KEY:-}" ]]; then
  read -r -s -p "DeepSeek API key (input hidden): " DEEPSEEK_API_KEY
  printf '\n'
fi
if [[ -z "$DEEPSEEK_API_KEY" ]]; then
  echo "No key entered; no API request was made." >&2
  exit 2
fi
export DEEPSEEK_API_KEY
export ANTHROPIC_BASE_URL="${ANTHROPIC_BASE_URL:-https://api.deepseek.com/anthropic}"
export ANTHROPIC_MODEL="${ANTHROPIC_MODEL:-deepseek-flash}"
cli_session_budget="${2:-0.04}"
extra_args=()
if [[ $# -ge 3 ]]; then
  if [[ "$3" != "--ignore-cumulative-budget" ]]; then
    echo "Unknown option: $3" >&2
    exit 2
  fi
  extra_args+=(--ignore-cumulative-budget)
fi

agentsight_bin="${AGENTSIGHT_BIN:-$repo_root/lab/agentsight/source/thesis_adapter/collector/target/release/agentsight}"
set +e
python3 "$repo_root/my_paper_coding/trace_adapter/run_agentsight_ebpf_real_canary.py" \
  --output "$1" \
  --agentsight-bin "$agentsight_bin" \
  --max-session-usd "$cli_session_budget" \
  "${extra_args[@]}"
status=$?
unset DEEPSEEK_API_KEY ANTHROPIC_AUTH_TOKEN ANTHROPIC_API_KEY
exit "$status"
