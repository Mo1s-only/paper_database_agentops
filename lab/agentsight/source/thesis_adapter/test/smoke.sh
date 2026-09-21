#!/usr/bin/env bash
# Minimal check: can Claude Code reach DeepSeek through the Anthropic-compatible
# endpoint at all? No AgentSight, no tools — isolate the LLM path first.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "${ROOT}/.env" ]; then set -a; . "${ROOT}/.env"; set +a; fi

export ANTHROPIC_BASE_URL="${ANTHROPIC_BASE_URL:-https://api.deepseek.com/anthropic}"
export ANTHROPIC_MODEL="${ANTHROPIC_MODEL:-deepseek-v4-pro}"
export CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1

echo "endpoint : ${ANTHROPIC_BASE_URL}"
echo "model    : ${ANTHROPIC_MODEL}"
echo "key set  : $([ -n "${ANTHROPIC_AUTH_TOKEN:-}" ] && echo yes || echo NO)"
echo

timeout 180 claude -p 'Reply with exactly: SMOKE_OK' \
    --output-format json \
    --model "${ANTHROPIC_MODEL}" \
    --allowedTools "Read"
echo "exit=$?"
