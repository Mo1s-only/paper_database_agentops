#!/usr/bin/env bash
# Install the pieces the AgentSight e2e test needs into WSL2.
# Idempotent: re-running skips anything already present.
set -uo pipefail

NODE_VERSION="${NODE_VERSION:-v22.14.0}"
NODE_DIR="/usr/local"
NODE_TARBALL="node-${NODE_VERSION}-linux-x64.tar.xz"

log() { echo "[setup] $*"; }

[ "$(uname -s)" = "Linux" ] || { echo "run this inside WSL2" >&2; exit 1; }

# --- agentsight ------------------------------------------------------------
if command -v agentsight >/dev/null 2>&1; then
    log "agentsight already installed: $(agentsight --version)"
else
    log "agentsight not found."
    log "The release binary is prebuilt for linux x86_64 — fetch it on a machine"
    log "that can reach GitHub, then place it at /usr/local/bin/agentsight:"
    log "  curl -L -o agentsight \\"
    log "    https://github.com/eunomia-bpf/agentsight/releases/latest/download/agentsight-x86_64"
    log "  scp agentsight <wsl-user>:/usr/local/bin/agentsight && chmod +x ..."
    exit 1
fi

# --- node ------------------------------------------------------------------
if command -v node >/dev/null 2>&1; then
    log "node already installed: $(node --version)"
else
    log "installing Node.js ${NODE_VERSION}..."
    curl -fsSL "https://nodejs.org/dist/${NODE_VERSION}/${NODE_TARBALL}" -o /tmp/node.tar.xz \
        || { echo "node download failed" >&2; exit 1; }
    tar -xJf /tmp/node.tar.xz -C "${NODE_DIR}" --strip-components=1
    rm -f /tmp/node.tar.xz
    log "node $(node --version), npm $(npm --version)"
fi

# --- claude code -----------------------------------------------------------
if command -v claude >/dev/null 2>&1; then
    log "claude already installed: $(claude --version 2>&1 | head -1)"
else
    log "installing Claude Code..."
    npm install -g @anthropic-ai/claude-code || { echo "npm install failed" >&2; exit 1; }
    log "claude $(claude --version 2>&1 | head -1)"
fi

# --- tracefs ---------------------------------------------------------------
# Not persistent across WSL restarts; run-test.sh re-mounts, this is a warm-up.
mount -t tracefs tracefs /sys/kernel/tracing 2>/dev/null || true
if [ -d /sys/kernel/tracing/events/sched/sched_process_exec ]; then
    log "tracefs OK — sched_process_exec tracepoint present"
else
    log "WARNING: sched_process_exec tracepoint not visible; eBPF probes will fail"
fi

log "done. Next: cp .env.example .env, add your key, then ./run-test.sh"
