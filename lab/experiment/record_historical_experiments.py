#!/usr/bin/env python3
"""Register pre-2026-10-10 experiments by hour without moving source artifacts."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime
import json
from pathlib import Path
import re
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
CUTOFF = datetime(2026, 10, 10, tzinfo=ZoneInfo("Asia/Shanghai"))


def earliest_file(path: Path):
    files = [item for item in path.rglob("*") if item.is_file()]
    if not files:
        return None, None
    item = min(files, key=lambda value: value.stat().st_mtime)
    return datetime.fromtimestamp(item.stat().st_mtime, ZoneInfo("Asia/Shanghai")), item


def timestamp_for(run_id: str, source: Path):
    utc = re.search(r"(20\d{6})T(\d{6})Z", run_id)
    if utc:
        value = datetime.strptime("".join(utc.groups()), "%Y%m%d%H%M%S").replace(tzinfo=ZoneInfo("UTC"))
        return value.astimezone(ZoneInfo("Asia/Shanghai")), "VERIFIED", "run_id_utc"
    local = re.search(r"(20\d{6})T(\d{6})", run_id)
    if local:
        value = datetime.strptime("".join(local.groups()), "%Y%m%d%H%M%S").replace(tzinfo=ZoneInfo("Asia/Shanghai"))
        return value, "VERIFIED", "run_id_local"
    value, evidence = earliest_file(source)
    if value is None:
        raise ValueError(f"No timestamp evidence for {source}")
    return value, "INFERRED", f"earliest_file_mtime:{evidence.resolve().relative_to(ROOT).as_posix()}"


def manifest_records():
    base = ROOT / "my_paper_coding/trace_adapter/structured_runs"
    index = json.loads((base / "run-index.json").read_text(encoding="utf-8"))
    records = []
    for item in index["runs"]:
        manifest_path = base / item["manifest"]
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        source = ROOT / manifest["source_root"]
        when, status, source_kind = timestamp_for(item["run_id"], source)
        records.append({"run_id": item["run_id"], "family": item["experiment_family"],
                        "run_kind": item["run_kind"], "framework": manifest.get("framework"),
                        "source_path": source.resolve().relative_to(ROOT).as_posix(),
                        "manifest_path": manifest_path.resolve().relative_to(ROOT).as_posix(),
                        "recorded_time": when.isoformat(), "time_status": status,
                        "time_evidence": source_kind, "artifact_count": len(manifest.get("artifacts", []))})
    return records


def extra_records():
    sources = []
    agentsight = ROOT / "lab/agentsight/results/experiments"
    if agentsight.exists():
        sources += [(path.name, "agentsight_e2e", path) for path in sorted(agentsight.iterdir()) if path.is_dir()]
    watson = ROOT / "lab/Watson/results/raw"
    if watson.exists():
        sources += [("watson-" + path.name, "watson", path) for path in sorted(watson.iterdir()) if path.is_dir()]
    records = []
    for run_id, family, source in sources:
        when, status, evidence = timestamp_for(run_id, source)
        artifact_count = sum(1 for item in source.rglob("*") if item.is_file())
        records.append({"run_id": run_id, "family": family, "run_kind": "run", "framework": None,
                        "source_path": source.resolve().relative_to(ROOT).as_posix(), "manifest_path": None,
                        "recorded_time": when.isoformat(), "time_status": status,
                        "time_evidence": evidence, "artifact_count": artifact_count})
    return records


def main() -> int:
    records = manifest_records() + extra_records()
    unique = {record["family"] + ":" + record["run_id"]: record for record in records}
    historical = [record for record in unique.values()
                  if datetime.fromisoformat(record["recorded_time"]) < CUTOFF]
    buckets = defaultdict(list)
    for record in historical:
        when = datetime.fromisoformat(record["recorded_time"])
        buckets[when.strftime("experiment_%Y%m%d_%H")].append(record)
    for folder, values in sorted(buckets.items()):
        target = HERE / folder
        target.mkdir(exist_ok=False)
        values.sort(key=lambda item: (item["recorded_time"], item["family"], item["run_id"]))
        (target / "runs.json").write_text(json.dumps(values, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        lines = [f"# {folder} 历史实验登记", "",
                 "> 本目录只建立索引，不移动或复制原始实验产物。", "",
                 "| 运行 | 类型 | 时间证据 | 原始路径 |", "|---|---|---|---|"]
        for value in values:
            lines.append(f"| `{value['run_id']}` | {value['family']} / {value['run_kind']} | "
                         f"{value['time_status']}: `{value['time_evidence']}` | `{value['source_path']}` |")
        (target / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    current = [path.name for path in sorted(HERE.glob("experiment_20*"))
               if path.is_dir() and path.name not in buckets]
    summary = {"schema_version": "agentops-experiment-index-v0.1", "timezone": "Asia/Shanghai",
               "directory_rule": "experiment_YYYYMMDD_HH", "historical_cutoff": CUTOFF.isoformat(),
               "historical_run_records": len(historical), "hour_directories": len(buckets),
               "current_hour_directories": current,
               "verified_time_records": sum(record["time_status"] == "VERIFIED" for record in historical),
               "inferred_time_records": sum(record["time_status"] == "INFERRED" for record in historical),
               "directories": [{"directory": folder, "run_count": len(values)}
                               for folder, values in sorted(buckets.items())] +
                              [{"directory": folder, "run_count": 1, "record_kind": "current"} for folder in current],
               "boundary": "Source paths are indexed in place; inferred hours use earliest surviving file mtime."}
    (HERE / "experiment_index.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
