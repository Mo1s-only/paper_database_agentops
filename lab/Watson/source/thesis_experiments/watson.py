#!/usr/bin/env python3
"""Watson-style, out-of-band cognitive observability over AgentSight SQLite.

This is a research reproduction, not a claim that generated explanations expose
hidden chain-of-thought. It stores provenance and labels every approximation.
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Protocol


@dataclass
class Call:
    id: str
    timestamp_ms: int
    model: str | None
    provider: str | None
    request: dict[str, Any]
    response: dict[str, Any]
    prompt: str
    output: str
    completion_kind: str
    source: str = "agentsight_sqlite"


def parse_json(value: str | None) -> dict[str, Any]:
    if not value or value == "null":
        return {}
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, dict) else {"value": parsed}
    except json.JSONDecodeError:
        return {"raw": value}


def text_from_message(message: Any) -> str:
    if isinstance(message, str):
        return message
    if isinstance(message, list):
        return "\n".join(text_from_message(x) for x in message)
    if isinstance(message, dict):
        if isinstance(message.get("text"), str):
            return message["text"]
        if isinstance(message.get("content"), str):
            return message["content"]
        if isinstance(message.get("content"), list):
            return text_from_message(message["content"])
    return ""


def normalize_request(raw: dict[str, Any]) -> str:
    if "messages" in raw:
        parts = []
        system = raw.get("system")
        if system:
            parts.append("[system]\n" + text_from_message(system))
        for message in raw.get("messages", []):
            role = message.get("role", "unknown") if isinstance(message, dict) else "unknown"
            parts.append(f"[{role}]\n{text_from_message(message)}")
        return "\n\n".join(p for p in parts if p.strip())
    return text_from_message(raw.get("prompt") or raw.get("input") or raw.get("json_content"))


def normalize_response(raw: dict[str, Any]) -> tuple[str, str]:
    choices_for_tools = raw.get("choices") or []
    if any((c.get("message") or {}).get("tool_calls") or (c.get("message") or {}).get("function_call") for c in choices_for_tools if isinstance(c, dict)) or any(isinstance(c, dict) and c.get("type") == "tool_use" for c in (raw.get("content") or []) if isinstance(raw.get("content"), list)):
        return "", "tool_or_unknown"
    if isinstance(raw.get("text_content"), str) and raw["text_content"].strip():
        return raw["text_content"], "text"
    choices = raw.get("choices")
    if isinstance(choices, list) and choices:
        choice = choices[0] if isinstance(choices[0], dict) else {}
        text = text_from_message(choice.get("message") or choice.get("text"))
        return text, "text" if text else "unknown"
    content = raw.get("content")
    text = text_from_message(content)
    if text:
        return text, "text"
    return "", "tool_or_unknown"


def extract_calls(db: Path) -> list[Call]:
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        rows = con.execute("""SELECT id, start_timestamp_ms, model, provider,
            request_body_json, response_body_json FROM llm_calls
            ORDER BY start_timestamp_ms""").fetchall()
    finally:
        con.close()
    calls: list[Call] = []
    for row in rows:
        request = parse_json(row["request_body_json"])
        response = parse_json(row["response_body_json"])
        prompt = normalize_request(request)
        output, kind = normalize_response(response)
        calls.append(Call(row["id"], row["start_timestamp_ms"], row["model"],
                     row["provider"], request, response, prompt, output, kind))
    return calls


def split_components(prompt: str) -> list[tuple[str, str]]:
    """Conservative, stable segmentation for ablation; never invents components."""
    chunks = [x.strip() for x in prompt.split("\n\n") if x.strip()]
    return [(f"component_{i}", text) for i, text in enumerate(chunks)] or [("component_0", prompt)]


class Client(Protocol):
    def complete(self, prompt: str, model: str, temperature: float, top_p: float) -> str: ...


class OpenAICompatibleClient:
    def __init__(self, base_url: str, api_key: str):
        self.url = base_url.rstrip("/") + "/chat/completions"
        self.api_key = api_key

    def complete(self, prompt: str, model: str, temperature: float, top_p: float) -> str:
        payload = json.dumps({"model": model, "temperature": temperature, "top_p": top_p,
            "messages": [{"role": "user", "content": prompt}]}).encode()
        request = urllib.request.Request(self.url, data=payload, method="POST",
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                data = json.loads(response.read())
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"model endpoint HTTP {exc.code}: {exc.read().decode(errors='replace')[:500]}") from exc
        return text_from_message(data.get("choices", [{}])[0].get("message", {}))


def reconstruction_prompt(prompt: str) -> str:
    # RepCoT samples from the input alone; the target is used only for rejection.
    return ("Solve the task independently and provide a concise explanation grounded in the input. "
        "End with the exact marker `FINAL: ` followed by your answer.\n\n"
        f"INPUT:\n{prompt}")


def matches_expected(candidate: str, expected: str) -> bool:
    marker = "FINAL:"
    final = candidate.rsplit(marker, 1)[-1].strip() if marker in candidate else ""
    return bool(final) and final == expected.strip()


def judge_prompt(reasoning: str, influential: list[tuple[str, str]]) -> str:
    evidence = "\n".join(f"- {name}: {text}" for name, text in influential)
    return ("Return only YES or NO. Is the candidate explanation grounded in, and semantically "
        "consistent with, the influential observed prompt components? Do not assess hidden CoT.\n"
        f"COMPONENTS:\n{evidence}\n\nCANDIDATE:\n{reasoning}")


def reconstruct(call: Call, client: Client, model: str, samples: int, temperature: float, top_p: float) -> dict[str, Any]:
    if call.completion_kind != "text" or not call.prompt or not call.output:
        return {"call_id": call.id, "status": "skipped", "reason": "requires text request and text completion"}
    if samples < 1:
        raise ValueError("samples must be positive")
    started = time.perf_counter()
    components = split_components(call.prompt)
    # PromptExp-compatible fallback: output reproducibility under leave-one-component-out ablation.
    ablations = []
    for name, _ in components:
        reduced = "\n\n".join(text for n, text in components if n != name)
        candidate = client.complete(reconstruction_prompt(reduced), model, temperature, top_p)
        ablations.append({"component": name, "target_match_without_component": matches_expected(candidate, call.output)})
    influential = [pair for pair, ablation in zip(components, ablations) if not ablation["target_match_without_component"]]
    accepted, attempts = [], 0
    matched, judged, history = 0, 0, []
    while len(accepted) < samples and attempts < samples * 4:
        attempts += 1
        candidate = client.complete(reconstruction_prompt(call.prompt), model, temperature, top_p)
        is_match = matches_expected(candidate, call.output)
        record = {"candidate": candidate, "output_match": is_match, "verdict": None}
        history.append(record)
        if not is_match:
            continue
        matched += 1
        judged += 1
        verdict = client.complete(judge_prompt(candidate, influential or components[:1]), model, 0.0, 1.0).strip().upper()
        record["verdict"] = verdict
        if verdict == "YES":
            accepted.append(candidate)
    summary_prompt = "Summarize the following accepted, observed-output-constrained explanations. " \
        "State uncertainty and do not claim access to hidden chain-of-thought.\n\n" + "\n\n---\n".join(accepted)
    summary = client.complete(summary_prompt, model, 0.0, 1.0) if accepted else "No verified candidate was accepted."
    return {"call_id": call.id, "status": "complete" if len(accepted) == samples else "insufficient_candidates", "mirror": {"model": model, "temperature": temperature, "top_p": top_p, "mirror_level": "approximate",
            "reason": "message roles flattened; full decoding configuration not replayed",
            "primary_model": call.model},
        "verification": {"method": "match_ablation", "components": ablations, "judge": "llm_yes_no", "output_matching": "exact_text",
            "limitations": "single-sample binary ablation; not token-probability PromptExp"},
        "requested_samples": samples, "attempts": attempts, "matched": matched,
        "output_match_rate": matched / attempts, "judge_acceptance_rate": len(accepted) / judged if judged else None,
        "api_requests": len(components) + attempts + judged + bool(accepted),
        "candidate_history": history, "accepted": len(accepted), "accepted_reasonings": accepted,
        "meta_reasoning": summary, "elapsed_seconds": round(time.perf_counter() - started, 3)}


def write_jsonl(path: Path, rows: list[Call]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(asdict(row), ensure_ascii=False) + "\n")


def read_jsonl(path: Path) -> list[Call]:
    return [Call(**json.loads(line)) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> int:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    export = commands.add_parser("export")
    export.add_argument("--db", required=True, type=Path); export.add_argument("--output", required=True, type=Path)
    recon = commands.add_parser("reconstruct")
    recon.add_argument("--input", required=True, type=Path); recon.add_argument("--output", required=True, type=Path)
    recon.add_argument("--base-url", required=True); recon.add_argument("--model", required=True)
    recon.add_argument("--api-key", default=os.getenv("WATSON_API_KEY")); recon.add_argument("--samples", type=int, default=10)
    recon.add_argument("--temperature", type=float, default=0.0); recon.add_argument("--top-p", type=float, default=1.0)
    args = parser.parse_args()
    if args.command == "export":
        calls = extract_calls(args.db); write_jsonl(args.output, calls)
        print(f"exported {len(calls)} AgentSight calls to {args.output}")
        return 0
    if not args.api_key:
        parser.error("--api-key or WATSON_API_KEY is required for real reconstruction")
    client = OpenAICompatibleClient(args.base_url, args.api_key)
    reports = [reconstruct(call, client, args.model, args.samples, args.temperature, args.top_p) for call in read_jsonl(args.input)]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"reproduction": "Watson RepCoT", "reports": reports}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {len(reports)} reports to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
