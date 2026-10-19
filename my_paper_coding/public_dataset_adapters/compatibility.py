from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from .common import TRUTH_FIELDS
from .validation import validate_record


@dataclass
class Metrics:
    records: int = 0
    schema_valid: int = 0
    fields_present: Counter[str] = field(default_factory=Counter)
    truth_present: Counter[str] = field(default_factory=Counter)
    truth_states: dict[str, Counter[str]] = field(
        default_factory=lambda: {name: Counter() for name in TRUTH_FIELDS}
    )
    relation_opportunities: int = 0
    relations_reconstructed: int = 0
    evidence_objects: int = 0
    evidence_complete: int = 0
    warnings: int = 0

    @staticmethod
    def _has_complete_evidence(obj: dict[str, Any]) -> bool:
        items = obj.get("evidence")
        if not isinstance(items, list) or not items:
            return False
        required = {"source_path", "json_pointer", "record_sha256", "support", "method"}
        return all(isinstance(item, dict) and required <= set(item) for item in items)

    def add(self, record: dict[str, Any]) -> None:
        self.records += 1
        errors = validate_record(record)
        if errors:
            raise ValueError(
                f"schema validation failed for {record.get('run', {}).get('run_id')}: {errors[:5]}"
            )
        self.schema_valid += 1

        run = record["run"]
        if run.get("run_id"):
            self.fields_present["run"] += 1
        if run.get("session_id"):
            self.fields_present["session"] += 1
        if record.get("agents"):
            self.fields_present["agent"] += 1
        if record.get("steps"):
            self.fields_present["step_span"] += 1
        if record.get("relations"):
            self.fields_present["relation"] += 1

        self.relation_opportunities += int(record["quality"].get("relation_opportunities", 0))
        self.relations_reconstructed += int(record["quality"].get("relations_reconstructed", 0))
        self.warnings += len(record["quality"].get("warnings", []))

        for item in record.get("steps", []):
            self.evidence_objects += 1
            self.evidence_complete += int(self._has_complete_evidence(item))
        for item in record.get("relations", []):
            self.evidence_objects += 1
            self.evidence_complete += int(self._has_complete_evidence(item))
        for field_name in TRUTH_FIELDS:
            label = record["truth"][field_name]
            state = label["state"]
            self.truth_states[field_name][state] += 1
            if state != "abstain":
                self.truth_present[field_name] += 1
                self.evidence_objects += 1
                self.evidence_complete += int(self._has_complete_evidence(label))

    @staticmethod
    def _rate(numerator: int, denominator: int) -> float | None:
        return round(numerator / denominator, 6) if denominator else None

    def as_dict(self) -> dict[str, Any]:
        total_truth_slots = self.records * len(TRUTH_FIELDS)
        abstentions = sum(counter["abstain"] for counter in self.truth_states.values())
        return {
            "records": self.records,
            "schema_valid_records": self.schema_valid,
            "schema_valid_rate": self._rate(self.schema_valid, self.records),
            "field_coverage": {
                key: {
                    "present": self.fields_present[key],
                    "rate": self._rate(self.fields_present[key], self.records),
                }
                for key in ("run", "session", "agent", "step_span", "relation")
            },
            "truth_coverage": {
                name: {
                    "present": self.truth_present[name],
                    "rate": self._rate(self.truth_present[name], self.records),
                    "states": dict(sorted(self.truth_states[name].items())),
                }
                for name in TRUTH_FIELDS
            },
            "relation_reconstruction": {
                "reconstructed": self.relations_reconstructed,
                "opportunities": self.relation_opportunities,
                "rate": self._rate(self.relations_reconstructed, self.relation_opportunities),
            },
            "evidence_completeness": {
                "complete": self.evidence_complete,
                "objects": self.evidence_objects,
                "rate": self._rate(self.evidence_complete, self.evidence_objects),
            },
            "abstention": {
                "slots": abstentions,
                "total_truth_slots": total_truth_slots,
                "rate": self._rate(abstentions, total_truth_slots),
            },
            "adapter_warnings": self.warnings,
        }


def convert_dataset(
    *,
    name: str,
    records: Iterable[dict[str, Any]],
    output_path: Path,
) -> dict[str, Any]:
    metrics = Metrics()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("x", encoding="utf-8", newline="\n") as handle:
        for record in records:
            metrics.add(record)
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    result = metrics.as_dict()
    result["dataset"] = name
    result["output"] = output_path.name
    return result


def aggregate(results: list[dict[str, Any]]) -> dict[str, Any]:
    total_records = sum(item["records"] for item in results)
    total_schema_valid = sum(item["schema_valid_records"] for item in results)
    reconstructed = sum(item["relation_reconstruction"]["reconstructed"] for item in results)
    opportunities = sum(item["relation_reconstruction"]["opportunities"] for item in results)
    evidence_complete = sum(item["evidence_completeness"]["complete"] for item in results)
    evidence_objects = sum(item["evidence_completeness"]["objects"] for item in results)
    abstain_slots = sum(item["abstention"]["slots"] for item in results)
    truth_slots = sum(item["abstention"]["total_truth_slots"] for item in results)

    def rate(num: int, den: int) -> float | None:
        return round(num / den, 6) if den else None

    return {
        "records": total_records,
        "schema_valid_records": total_schema_valid,
        "schema_valid_rate": rate(total_schema_valid, total_records),
        "relation_reconstruction_rate": rate(reconstructed, opportunities),
        "relation_reconstructed": reconstructed,
        "relation_opportunities": opportunities,
        "evidence_completeness_rate": rate(evidence_complete, evidence_objects),
        "evidence_complete_objects": evidence_complete,
        "evidence_objects": evidence_objects,
        "abstention_rate": rate(abstain_slots, truth_slots),
        "abstention_slots": abstain_slots,
        "truth_slots": truth_slots,
        "adapter_warnings": sum(item["adapter_warnings"] for item in results),
    }


def percent(value: float | None) -> str:
    return "N/A" if value is None else f"{value * 100:.2f}%"


def report_markdown(report: dict[str, Any]) -> str:
    rows = []
    for item in report["datasets"]:
        fields = item["field_coverage"]
        rows.append(
            "| {dataset} | {records} | {schema} | {run} | {agent} | {step} | {relation} | {rebuild} | {evidence} | {abstain} | {warnings} |".format(
                dataset=item["dataset"],
                records=item["records"],
                schema=percent(item["schema_valid_rate"]),
                run=percent(fields["run"]["rate"]),
                agent=percent(fields["agent"]["rate"]),
                step=percent(fields["step_span"]["rate"]),
                relation=percent(fields["relation"]["rate"]),
                rebuild=percent(item["relation_reconstruction"]["rate"]),
                evidence=percent(item["evidence_completeness"]["rate"]),
                abstain=percent(item["abstention"]["rate"]),
                warnings=item["adapter_warnings"],
            )
        )
    truth_sections = []
    for item in report["datasets"]:
        truth_rows = "\n".join(
            f"| {name} | {value['present']}/{item['records']} | {percent(value['rate'])} | `{json.dumps(value['states'], ensure_ascii=False, sort_keys=True)}` |"
            for name, value in item["truth_coverage"].items()
        )
        truth_sections.append(
            f"### {item['dataset']}\n\n| 真值类型 | 有标签记录 | 覆盖率 | 状态分布 |\n|---|---:|---:|---|\n{truth_rows}"
        )
    overall = report["overall"]
    return f"""# 公开归因数据统一协议兼容性报告

运行时间：{report['generated_at']}  
协议：`attribution-benchmark-record-v0.1`

## 汇总

| 数据集 | 记录 | Schema有效 | Run覆盖 | Agent覆盖 | Step/span覆盖 | Relation覆盖 | 关系重建率 | 证据完整率 | 真值拒绝率 | 警告 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
{chr(10).join(rows)}

总计处理 **{overall['records']}** 条记录；schema 有效率 **{percent(overall['schema_valid_rate'])}**，关系重建率 **{percent(overall['relation_reconstruction_rate'])}**，证据完整率 **{percent(overall['evidence_completeness_rate'])}**，五类真值槽位拒绝率 **{percent(overall['abstention_rate'])}**。

拒绝率表示源数据没有提供相应粒度真值，是诚实保留的数据边界，不是适配器失败率。

## 五类真值覆盖

{chr(10).join(truth_sections)}

## 解释边界

- Who&When 的相邻 history 只形成时间顺序边，不声称错误传播边。
- TRAIL 的错误 span 标为 `partial` responsibility step，不提升为决定性根因。
- AgentTrace 的传播边只有在 causal path 的相邻节点能匹配原始图边时才记为 `derived`。
- 本报告评价数据兼容性，不评价任何归因算法的准确率。
"""

