from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from . import agenttrace_adapter, trail_adapter, who_when_adapter
from .compatibility import aggregate, convert_dataset, report_markdown


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Normalize public attribution datasets and measure compatibility.")
    parser.add_argument("--who-when", required=True, type=Path)
    parser.add_argument("--trail", required=True, type=Path)
    parser.add_argument("--agenttrace", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.output.exists():
        raise FileExistsError(f"Refusing to overwrite existing output directory: {args.output}")
    args.output.mkdir(parents=True)
    results = [
        convert_dataset(
            name="Who&When",
            records=who_when_adapter.iter_records(args.who_when),
            output_path=args.output / "who-and-when.jsonl",
        ),
        convert_dataset(
            name="TRAIL",
            records=trail_adapter.iter_records(args.trail),
            output_path=args.output / "trail.jsonl",
        ),
        convert_dataset(
            name="AgentTrace",
            records=agenttrace_adapter.iter_records(args.agenttrace),
            output_path=args.output / "agenttrace.jsonl",
        ),
    ]
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "schema": "attribution-benchmark-record-v0.1",
        "datasets": results,
        "overall": aggregate(results),
    }
    (args.output / "compatibility-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (args.output / "compatibility-report.md").write_text(report_markdown(report), encoding="utf-8")
    print(json.dumps(report["overall"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
