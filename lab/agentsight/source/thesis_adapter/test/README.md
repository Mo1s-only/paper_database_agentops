# AgentSight end-to-end test: observe Claude Code on DeepSeek

This test proves AgentSight's core claim on a real agent: run Claude Code
backed by the DeepSeek API, and verify that prompts, model calls, tokens,
tool calls and file writes were actually captured at the system boundary —
no SDK, no proxy, no vendor integration.

**Result on this machine: 13/13 checks pass.**

```
4 API calls · 116.6k tokens · 12 execs · 2 files · 2 network endpoints
deepseek-v4-pro   45104 in   391 out   71086 cache_read   116581 total   4 calls
claude  deepseek-v4-pro  58334  "Create a file named hello.txt in the current
                                  directory containing exactly the line: ..."
```

## Why this test must run inside WSL2

AgentSight observes agents with eBPF, which needs a Linux kernel. Windows
itself cannot run it. WSL2 provides a real Linux kernel, so the observed agent
**must also run inside WSL2** — eBPF sees only that VM's own processes, not
Windows processes.

| Requirement | Status on this machine |
| --- | --- |
| WSL2 kernel | `6.18.33.2-microsoft-standard-WSL2` |
| tracefs mounted at `/sys/kernel/tracing` | **required** — see gotcha 1 |
| `agentsight` binary | `/usr/local/bin/agentsight` (v1.0.31, x86_64) |
| Node.js + Claude Code | `./setup.sh` |
| DeepSeek Anthropic endpoint | `https://api.deepseek.com/anthropic` |

## Two WSL2 gotchas this test works around

Both were found by bisecting the capture path; `./diagnostics.sh` re-checks
them. Without these, every run silently produces an empty session.

### 1. tracefs is not mounted by default

libbpf resolves tracepoint perf event IDs through tracefs. If it is missing,
every probe fails to attach:

```
libbpf: failed to determine tracepoint 'sched/sched_process_exec' perf event ID: -ENOENT
libbpf: prog 'handle_exec': failed to auto-attach: -ENOENT
```

`run-test.sh` mounts it first. Mounts do not survive a WSL restart, which is
why this happens on every run rather than once at setup.

### 2. `record`'s launch mode captures nothing — use attach mode

`agentsight record -- <command>` attaches cleanly, the BPF programs load
(verifiable as `bpf-prog` fds on the `sslsniff` / `stdiocap` / `process`
helpers), and the target execs normally — but **zero events reach the DB**,
even for a trivial `echo`. Meanwhile `agentsight debug process` streams every
event from the same kernel, so the eBPF layer itself is healthy and the loss
is in launch-mode session attribution.

`run-test.sh` therefore starts the monitor first and attaches by command name
— the documented `agentsight record -c claude` flow:

```bash
agentsight record -c claude --db session.db --no-server &   # start FIRST
sleep 2
claude -p "..."                                             # agent runs inside the window
```

Attaching by PID (`-p`) did not work either; comm-match mode did.

## Setup

```bash
# inside WSL2
cd /mnt/c/Users/mobao/Desktop/agentsight/test
cp .env.example .env     # then put your real key in .env
./setup.sh               # installs Node.js + Claude Code if missing
```

`.env` holds the API key and is git-ignored. Never commit it.

## Run

```bash
./run-test.sh     # capture
./verify.sh       # assert, exit non-zero on failure
```

Other entry points:

- `./smoke.sh` — checks the Claude Code → DeepSeek path alone, no AgentSight.
  Run this first when something breaks; it isolates the LLM side.
- `./diagnostics.sh` — re-checks the kernel/probe/mode assumptions above.
- `python3 inspect-db.py [db]` — dumps per-table row counts from a session DB.
  Used by `verify.sh` as ground truth, independent of report formatting.

## What is asserted

| Tier | Checks |
| --- | --- |
| agent ran | Claude Code returned a result; `hello.txt` exists with the right content |
| eBPF process | `process_nodes`, `audit_events` non-zero; agent exec attributed to `claude` |
| TLS / LLM | `llm_calls`, `token_usage` non-zero; model name, token counts, prompt text captured |
| tools / net | `tool_calls`, `network_targets` non-zero |

The tiering matters: the file effect and the LLM capture come from different
probes, so a partial failure tells you which layer broke.

## Notes

- The agent is launched with `--allowedTools "Write" "Read"` — no Bash, no
  network. That is enough to produce a real tool call and a real file effect
  without handing the agent a general-purpose shell.
- Claude Code 2.x is a Bun-compiled binary with embedded BoringSSL and no
  `SSL_write` symbol. AgentSight detects the BoringSSL byte pattern and
  attaches the uprobes by offset; LLM capture works despite the warning:

  ```
  libbpf: elf: 'SSL_write' is 0 in symtab ...: try using shared library path instead
  BoringSSL byte-pattern detected in claude.exe. Attaching by offset...
  ```

- `agentsight report summary` falls back to reading Claude Code's own
  transcripts ("agent_native_session") instead of the recorded DB, so it
  reports session totals across all runs rather than just this one. The
  DB-backed subcommands (`report token` / `prompts` / `audit`) are the ones
  that reflect the actual capture — `verify.sh` checks those.
- DeepSeek exposes `deepseek-flash` and `deepseek-v4-pro`. Claude Code prints
  `[claude-code:unrecognized_model]` for both since they are not in its
  built-in registry; this is cosmetic and the calls succeed.
