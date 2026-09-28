#!/usr/bin/env python3
"""Read Claude JSON logs and build a local API cost ledger. No network calls."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def objects_from_file(path: Path):
    text = path.read_text(encoding="utf-8", errors="replace")
    candidates = [text] + [line for line in text.splitlines() if line.strip()]
    seen = set()
    for candidate in candidates:
        try:
            obj = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        marker = json.dumps(obj, sort_keys=True, ensure_ascii=False)
        if marker not in seen:
            seen.add(marker)
            yield obj


def extract(path: Path) -> dict | None:
    found = None
    for obj in objects_from_file(path):
        if not isinstance(obj, dict):
            continue
        usage = obj.get("usage")
        model_usage = obj.get("modelUsage")
        cost = obj.get("total_cost_usd")
        if cost is None and isinstance(model_usage, dict):
            cost = sum(float(v.get("costUSD", 0) or 0) for v in model_usage.values() if isinstance(v, dict))
        if cost is None and not isinstance(usage, dict):
            continue
        found = {
            "path": str(path),
            "session_id": obj.get("session_id"),
            "model": next(iter(model_usage), None) if isinstance(model_usage, dict) else None,
            "cost_usd": float(cost or 0),
            "input_tokens": int((usage or {}).get("input_tokens", 0) or 0),
            "output_tokens": int((usage or {}).get("output_tokens", 0) or 0),
            "cache_read_tokens": int((usage or {}).get("cache_read_input_tokens", 0) or 0),
            "is_error": bool(obj.get("is_error", False)),
        }
    return found


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, action="append", required=True)
    parser.add_argument("--json-out", type=Path, required=True)
    parser.add_argument("--markdown-out", type=Path, required=True)
    args = parser.parse_args()
    paths = []
    for root in args.root:
        if root.exists():
            paths.extend(sorted(p for p in root.rglob("*") if p.is_file() and (p.name == "claude.json" or p.name == "claude-run.log" or p.name.startswith("claude-agent-") and p.suffix == ".log")))
    entries = []
    seen_sessions = set()
    for path in paths:
        entry = extract(path)
        if entry is None:
            continue
        key = (entry.get("session_id"), entry.get("cost_usd"), entry.get("path"))
        if key in seen_sessions:
            continue
        seen_sessions.add(key)
        entries.append(entry)
    total = sum(x["cost_usd"] for x in entries)
    summary = {"files_scanned": len(paths), "priced_runs": len(entries), "total_cost_usd": round(total, 6), "max_single_run_usd": round(max((x["cost_usd"] for x in entries), default=0), 6), "entries": entries, "source_policy": "local logs only; no API calls"}
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = ["# API 成本账本", "", "> 仅解析本地 Claude JSON 日志，本次生成没有发起 API 请求。", "", f"- 扫描文件数：{len(paths)}", f"- 可计价运行数：{len(entries)}", f"- 累计成本（USD）：{total:.6f}", f"- 单次最高成本（USD）：{max((x['cost_usd'] for x in entries), default=0):.6f}", "", "| 日志 | 模型 | 成本 USD | 输入 token | 输出 token |", "|---|---|---:|---:|---:|"]
    for x in entries:
        lines.append(f"| `{x['path']}` | {x.get('model') or '-'} | {x['cost_usd']:.6f} | {x['input_tokens']} | {x['output_tokens']} |")
    args.markdown_out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"priced_runs": len(entries), "total_cost_usd": round(total, 6), "max_single_run_usd": round(max((x["cost_usd"] for x in entries), default=0), 6)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
