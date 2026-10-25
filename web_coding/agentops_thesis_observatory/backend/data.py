"""Evidence-backed local experiment registry and read-only historical adapters.

Only the registry and newly created run directories are written. Imported source
artifacts stay in place; absent measurements remain None throughout the API.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import mimetypes
import re
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from urllib.parse import quote


PLATFORM = Path(__file__).resolve().parents[1]
DEFAULT_REPO = PLATFORM.parents[1]
TEXT_SUFFIXES = {".json", ".jsonl", ".md", ".txt", ".csv", ".tsv", ".py"}
IMAGE_SUFFIXES = {".svg", ".png", ".jpg", ".jpeg", ".webp"}
DENIED_NAME = re.compile(r"(?:^\.|^private$|credential|secret|password|token|\.env|stderr|stdout|raw.stream|receipt.times|launch\.json)", re.I)
SENSITIVE_KEY = re.compile(r"^(?:authorization|api[-_]?key|.*_api_key|(?:.*_)?auth_token|access_token|refresh_token|password|secret|credentials?)$", re.I)
PRIVATE_COLUMN = re.compile(r"(?:request_body|response_body|input_json|output_json|argv|command|prompt|headers|payload)", re.I)
TOKEN = re.compile(r"(?i)(Bearer\s+)[A-Za-z0-9._~+/=-]+|\b(?:sk|sk-ant)-[A-Za-z0-9_-]{12,}")
TERMINAL = {"completed", "partial", "failed", "interrupted", "stopped"}


def now():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def load(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError, UnicodeError):
        return default


def scrub(value):
    if isinstance(value, dict):
        return {str(k): "[REDACTED]" if SENSITIVE_KEY.match(str(k)) else scrub(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [scrub(v) for v in value]
    if isinstance(value, bytes):
        return "<binary: %s bytes>" % len(value)
    if isinstance(value, str):
        return TOKEN.sub(lambda m: (m.group(1) or "") + "[REDACTED]", value)
    return value


def jsonl(path, limit=20000):
    """Read a bounded prefix; incomplete final lines during capture are ignored."""
    result = []
    try:
        with Path(path).open(encoding="utf-8-sig") as stream:
            for index, line in enumerate(stream):
                if index >= limit:
                    break
                try:
                    row = json.loads(line)
                    if isinstance(row, dict):
                        result.append(row)
                except ValueError:
                    continue
    except (OSError, UnicodeError):
        pass
    return result


def under(path, root):
    try:
        Path(path).resolve().relative_to(Path(root).resolve())
        return True
    except ValueError:
        return False


def timestamp(path):
    try:
        return datetime.fromtimestamp(Path(path).stat().st_mtime, timezone.utc).isoformat(timespec="seconds")
    except OSError:
        return None


def integer(value):
    return value if isinstance(value, int) and not isinstance(value, bool) else None


class Repository:
    def __init__(self, runtime_dir=None, run_root=None, repo=None, discover=True):
        self.repo = Path(repo or DEFAULT_REPO).resolve()
        self.runtime_dir = Path(runtime_dir or PLATFORM / "runtime").resolve()
        self.run_root = Path(run_root or self.repo / "lab/experiment/observatory_runs").resolve()
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self.run_root.mkdir(parents=True, exist_ok=True)
        self.registry_path = self.runtime_dir / "registry.sqlite3"
        self._lock = threading.RLock()
        self._db_cache = {}
        with self._connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY, root TEXT UNIQUE NOT NULL, record TEXT NOT NULL)")
        if discover:
            self.discover()

    @contextmanager
    def _connect(self):
        connection = sqlite3.connect(self.registry_path, timeout=10)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _relative(self, path):
        try:
            return Path(path).resolve().relative_to(self.repo).as_posix()
        except ValueError:
            return str(path)

    def catalog(self):
        specs = [
            ("error-propagation-v1", "错误传播 · 双 Agent", "cross_layer_live", "controlled_recipe", "my_paper_coding/trace_adapter/capture_real_scenarios.py", 1,
             "受控单任务：Agent A 观测服务并写 handoff.json，Agent B 根据交接文件写 decision.json。故障注入属于任务输入；平台运行成功与任务预期失败分别记录。", True, 0.10),
            ("routing-error-v1", "角色路由错误 · 双 Agent", "cross_layer_live", "controlled_recipe", "my_paper_coding/trace_adapter/capture_real_scenarios.py", 1,
             "受控单任务：Agent A 生成路由选择，Agent B 执行被选角色。保留真实 CLI、AgentSight 与精确工具 ID 对齐证据。", True, 0.10),
            ("who-when", "Who & When · 本地归一化输入", "input_audit", "public_normalized", "lab/experiment/experiment_20261016_16/results_r3/who-and-when.jsonl", None,
             "核验已有公开数据适配记录及字段；读取本地 JSONL，不调用外部 API，不产生新的运行时跨层证据。", False, 0),
            ("trail", "TRAIL · 本地归一化输入", "input_audit", "public_normalized", "lab/experiment/experiment_20261016_16/results_r3/trail.jsonl", None,
             "核验本地 TRAIL 适配输入；历史公开轨迹的语义结构不能作为本次系统采集证明。", False, 0),
            ("agenttrace", "AgentTrace · 本地归一化输入", "input_audit", "public_normalized", "lab/experiment/experiment_20261016_16/results_r3/agenttrace.jsonl", None,
             "核验本地 AgentTrace 适配输入及样本字段；不重新执行原始任务。", False, 0),
            ("alignment-stress-1000", "关联边界 · 1000 条合成输入", "input_audit", "synthetic_fixture", "my_paper_coding/trace_adapter/fixtures/alignment_stress_1000.jsonl", None,
             "明确标注的合成 fixture，用于核验输入完整性；不代表真实 API、eBPF 或跨层关联效果。", False, 0),
        ]
        result = []
        for identifier, name, kind, input_kind, source, count, description, api, budget in specs:
            path = self.repo / source
            if path.is_file() and count is None:
                try:
                    with path.open(encoding="utf-8-sig") as stream:
                        count = sum(1 for line in stream if line.strip())
                except (OSError, UnicodeError):
                    pass
            result.append(dict(id=identifier, name=name, experiment_type=kind,
                description=description, input_kind=input_kind, record_count=count,
                source_path=source, source_url=f"/api/datasets/{quote(identifier)}/source",
                api_required=api, available=path.is_file(), budget_usd=budget))
        return result

    def _save(self, record):
        with self._lock, self._connect() as db:
            db.execute("INSERT INTO runs(id, root, record) VALUES(?,?,?) ON CONFLICT(id) DO UPDATE SET root=excluded.root, record=excluded.record",
                       (record["id"], record["root"], json.dumps(record, ensure_ascii=False)))
        return record

    def get_run(self, identifier):
        with self._lock, self._connect() as db:
            row = db.execute("SELECT record FROM runs WHERE id=?", (identifier,)).fetchone()
        return json.loads(row[0]) if row else None

    def list_runs(self):
        with self._lock, self._connect() as db:
            records = [json.loads(row[0]) for row in db.execute("SELECT record FROM runs")]
        fields = ("id", "name", "dataset_id", "dataset_name", "status", "created_at", "source_kind", "summary")
        return [{key: record.get(key) for key in fields} for record in sorted(records, key=lambda x: x.get("created_at") or "", reverse=True)]

    def new_run(self, name, dataset_id):
        dataset = next((d for d in self.catalog() if d["id"] == dataset_id), None)
        if not dataset:
            raise ValueError("数据集不在目录中")
        identifier = "run-" + datetime.now().strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:8]
        root = self.run_root / identifier
        root.mkdir(parents=True, exist_ok=False)
        record = dict(id=identifier, root=str(root), name=name or dataset["name"], dataset_id=dataset_id,
                      dataset_name=dataset["name"], experiment_type=dataset["experiment_type"], status="queued",
                      created_at=now(), finished_at=None, source_kind="platform", summary="等待执行", timeline=[])
        self._save(record)
        self._state(record)
        return record

    def _state(self, record):
        if record.get("source_kind") == "platform":
            path = Path(record["root"]) / "state.json"
            temp = path.with_suffix(".json.tmp")
            temp.write_text(json.dumps(scrub(record), ensure_ascii=False, indent=2), encoding="utf-8")
            temp.replace(path)

    def update(self, identifier, **changes):
        with self._lock:
            record = self.get_run(identifier)
            if not record:
                raise KeyError(identifier)
            changes.pop("id", None)
            changes.pop("root", None)
            record.update(scrub(changes))
            if str(record.get("status", "")).lower() in TERMINAL and not record.get("finished_at"):
                record["finished_at"] = now()
            self._save(record)
            self._state(record)
            return record

    def event(self, identifier, stage, message, **extra):
        with self._lock:
            record = self.get_run(identifier)
            if not record:
                raise KeyError(identifier)
            event = scrub(dict(at=now(), stage=stage, message=message, **extra))
            record.setdefault("timeline", []).append(event)
            record["stage"] = stage
            self._save(record)
            if record.get("source_kind") == "platform":
                with (Path(record["root"]) / "lifecycle.jsonl").open("a", encoding="utf-8") as stream:
                    stream.write(json.dumps(event, ensure_ascii=False) + "\n")
            self._state(record)
            return event

    def _capture(self, root):
        direct = root / "capture-summary.json"
        if direct.is_file():
            return direct, self._enrich_capture(direct, load(direct, {}))
        candidates = sorted(root.glob("*/capture-summary.json"))
        if candidates:
            return candidates[0], self._enrich_capture(candidates[0], load(candidates[0], {}))
        return None, {}

    def _enrich_capture(self, path, capture):
        if not isinstance(capture, dict):
            return {}
        if not capture.get("agents"):
            agents = [load(p, {}) for p in sorted(path.parent.glob("agent_*-capture-summary.json"))]
            if agents:
                capture["agents"] = agents
        return capture

    def discover(self):
        """Import independent run roots; no rewriting, copying, or SQLite migration."""
        base = self.repo / "lab/experiment"
        if not base.is_dir():
            return self.list_runs()
        candidates = set()
        for pattern in ("*.db", "*.sqlite", "*.sqlite3", "capture-summary.json", "state.json"):
            for marker in base.rglob(pattern):
                if marker.is_file() and under(marker, base) and not under(marker, self.runtime_dir):
                    candidates.add(marker.parent.resolve())
        state_roots = {p for p in candidates if (p / "state.json").is_file()}
        # Old controller batch directories own their scenario subdirectories.
        candidates = {p for p in candidates if not any(p != s and under(p, s) for s in state_roots)}
        datasets = {d["id"]: d for d in self.catalog()}
        with self._connect() as db:
            previous = {row["root"]: json.loads(row["record"]) for row in db.execute("SELECT root,record FROM runs")}
            for old_root in previous:
                if not Path(old_root).exists():
                    db.execute("DELETE FROM runs WHERE root=?", (old_root,))
        for root in sorted(candidates):
            existing = previous.get(str(root))
            if existing and existing.get("source_kind") == "platform":
                continue
            state = load(root / "state.json", {})
            plan = load(root / "plan.json", {})
            capture_path, capture = self._capture(root)
            if not isinstance(state, dict):
                state = {}
            if not isinstance(capture, dict):
                capture = {}
            identifier = str(state.get("id") or state.get("run_id") or root.name)
            clash = self.get_run(identifier)
            if clash and clash["root"] != str(root):
                identifier += "-" + hashlib.sha256(str(root).encode()).hexdigest()[:8]
            dataset_id = state.get("dataset_id") or capture.get("scenario") or plan.get("scenario")
            public_name = capture.get("dataset") or plan.get("dataset")
            if not dataset_id and public_name:
                dataset_id = {"AgentTrace": "agenttrace", "TRAIL": "trail", "Who&When": "who-when", "Who & When": "who-when", "WhoAndWhen": "who-when"}.get(public_name, str(public_name).lower())
            dataset_id = dataset_id or "historical-unregistered"
            status = str(state.get("status", "")).lower()
            if status not in TERMINAL | {"queued", "running"}:
                # A completed CLI run may intentionally produce a failing task.
                agents = capture.get("agents") or ([capture] if "success" in capture else [])
                if capture and agents and all(agent.get("success") is True for agent in agents):
                    status = "completed"
                elif capture:
                    status = "partial"
                else:
                    status = "partial"
            source_kind = "platform" if under(root, self.run_root) and state.get("source_kind") == "platform" else "historical"
            result = state.get("result") or {}
            summary = state.get("summary") or result.get("note") or ("历史采集工件已登记；打开查看真实会话与关联证据" if capture else "历史 SQLite 工件；会话摘要或关联报告可能缺失")
            record = dict(id=identifier, root=str(root), name=state.get("name") or root.name,
                dataset_id=dataset_id, dataset_name=datasets.get(dataset_id, {}).get("name") or public_name or "历史输入（未登记）",
                status=status, source_kind=source_kind,
                created_at=state.get("created_at") or self._run_time(root, capture_path, plan),
                finished_at=state.get("finished_at"), summary=summary,
                timeline=state.get("timeline") or state.get("events") or [],
                stage=state.get("stage"), result=result, error=state.get("error"), experiment_type=state.get("experiment_type"))
            self._save(record)
        return self.list_runs()

    def _run_time(self, root, capture_path, plan):
        # Launch files carry actual invocation time; do not guess from run names.
        launch = load(root / "agent_a-launch.json", {})
        for key in ("launched_at", "started_at", "created_at", "start_time", "timestamp"):
            if isinstance(launch.get(key), str):
                return launch[key]
        for key in ("start_ms", "started_ms", "launch_epoch_ms"):
            if isinstance(launch.get(key), (int, float)):
                return datetime.fromtimestamp(launch[key] / 1000, timezone.utc).isoformat(timespec="seconds")
        process_start = (launch.get("process") or {}).get("start_ms")
        if isinstance(process_start, (int, float)):
            return datetime.fromtimestamp(process_start / 1000, timezone.utc).isoformat(timespec="seconds")
        events = jsonl(root / "parsed/application-events.jsonl", limit=1)
        if events and isinstance(events[0].get("timestamp_ms"), (int, float)):
            return datetime.fromtimestamp(events[0]["timestamp_ms"] / 1000, timezone.utc).isoformat(timespec="seconds")
        return plan.get("created_at") or timestamp(root / "plan.json") or timestamp(capture_path or root)

    def _database_paths(self, root):
        paths = set()
        for suffix in ("*.db", "*.sqlite", "*.sqlite3"):
            paths.update(path.resolve() for path in root.rglob(suffix) if path.is_file() and under(path, root))
        return sorted(paths, key=str)

    @contextmanager
    def _read_db(self, path):
        # mode=ro respects a live WAL without modifying the source database.
        connection = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=2)
        connection.execute("PRAGMA query_only=ON")
        try:
            yield connection
        finally:
            connection.close()

    def _inventory(self, root):
        files, counts = [], {}
        for index, path in enumerate(self._database_paths(root)):
            try:
                stamp = (path.stat().st_mtime_ns, path.stat().st_size,
                         Path(str(path) + "-wal").stat().st_mtime_ns if Path(str(path) + "-wal").exists() else None)
                cached = self._db_cache.get(str(path))
                if cached and cached[0] == stamp:
                    tables = cached[1]
                else:
                    tables = []
                    with self._read_db(path) as db:
                        names = [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
                        for name in names:
                            quoted = '"' + name.replace('"', '""') + '"'
                            try:
                                count = db.execute(f"SELECT COUNT(*) FROM {quoted}").fetchone()[0]
                            except sqlite3.Error:
                                count = None
                            tables.append(dict(name=name, rows=count))
                    self._db_cache[str(path)] = (stamp, tables)
                files.append(dict(id=index, name=path.name, path=self._relative(path), tables=tables,
                                  evidence_scope="offline_input" if path.name == "input.sqlite" else "recorded_database"))
                for table in tables:
                    name, count = table["name"], table["rows"]
                    counts[name] = None if count is None or (name in counts and counts[name] is None) else counts.get(name, 0) + count
            except (OSError, sqlite3.Error) as error:
                files.append(dict(id=index, name=path.name, path=self._relative(path), tables=[], error=type(error).__name__))
        return dict(files=files, counts=counts)

    def database_preview(self, identifier, db_index, table):
        record = self.get_run(identifier)
        if not record:
            return None
        paths = self._database_paths(Path(record["root"]))
        try:
            index = int(db_index)
            if index < 0:
                return None
            path = paths[index]
        except (IndexError, ValueError, TypeError):
            return None
        with self._read_db(path) as db:
            names = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
            if table not in names:
                return None
            escaped = '"' + table.replace('"', '""') + '"'
            total = db.execute(f"SELECT COUNT(*) FROM {escaped}").fetchone()[0]
            cursor = db.execute(f"SELECT * FROM {escaped} LIMIT 100")
            columns = [col[0] for col in cursor.description]
            rows = []
            for row in cursor:
                rows.append(["[REDACTED]" if SENSITIVE_KEY.match(column) or PRIVATE_COLUMN.search(column) else scrub(value[:4000] if isinstance(value, str) else value)
                             for column, value in zip(columns, row)])
            return dict(columns=columns, rows=rows, total=total, truncated=total > len(rows))

    def _comparisons(self, root):
        paths = sorted(root.rglob("real-alignment-comparison.json"))
        # Prefer the explicit final audited profile over intermediate experiments.
        paths.sort(key=lambda p: ("v2-final" in str(p), "controlled-profile-final" in str(p), "tool-bridge" in str(p), p.stat().st_mtime_ns), reverse=True)
        for path in paths:
            value = load(path, {})
            if isinstance(value, dict) and value:
                return path, value
        return None, {}

    def _api(self, capture, record):
        agents = capture.get("agents") or []
        if not agents and "success" in capture:
            agents = [capture]
        sessions = integer(capture.get("actual_cli_sessions"))
        if sessions is None:
            sessions = integer(capture.get("api_sessions"))
        if sessions is None and agents:
            sessions = len(agents)
        successful = sum(a.get("success") is True for a in agents) if agents else None
        cost = capture.get("reported_cost_usd")
        if not isinstance(cost, (int, float)):
            cost = None
        session_costs = [a["reported_cost_usd"] for a in agents
                         if isinstance(a.get("reported_cost_usd"), (int, float)) and not isinstance(a.get("reported_cost_usd"), bool)]
        known_cost = sum(session_costs) if session_costs else None
        # The capture script sums missing session costs as zero. It is not a
        # measured zero bill, and an incomplete total must stay unknown.
        if capture.get("cost_complete") is False:
            cost = None
        models = sorted({name for a in agents for name in (a.get("modelUsage") or a.get("model_usage") or {})})
        if agents and any(a.get("session_id") and a.get("success") is True for a in agents) and cost is not None:
            status, label = "confirmed", "真实 CLI 会话已确认"
        elif capture:
            status, label = "partial", "存在采集摘要，调用完成证据不完整"
        elif record.get("experiment_type") == "input_audit" or record.get("dataset_id") in {"who-when", "trail", "agenttrace", "alignment-stress-1000"} and record.get("source_kind") == "platform":
            status, label, sessions, successful, cost = "not_required", "离线输入核验，无需 API", 0, 0, 0
        else:
            status, label = "unknown", "没有会话摘要，API 调用情况未知"
        return dict(status=status, label=label, sessions=sessions, successful_sessions=successful, cost_usd=cost,
                    known_cost_usd=known_cost, cost_complete=capture.get("cost_complete"), http_successes=None, models=models,
                    scope="会话数来自 CLI capture-summary；费用为 CLI 自报，非供应商最终账单。HTTP 请求成功次数未独立测量。")

    def _correlation(self, comparison):
        native, system = integer(comparison.get("native_tool_starts")), integer(comparison.get("system_tool_ids"))
        modes = {}
        for mode, counts in (comparison.get("identity_modes") or {}).items():
            modes[mode] = dict(accepted=counts.get("accepted", 0), abstain=counts.get("abstain", 0))
        controlled = comparison.get("controlled_instrumentation_profile") or {}
        profile = controlled.get("status_counts")
        bridge = dict(accepted=profile.get("accepted", 0) if profile else None,
                      abstain=profile.get("abstain", 0) if profile else None,
                      label="受控 Bash 钩子 → eBPF 子进程血缘（单独审计）",
                      scope=controlled.get("boundary") or "尚未生成受控进程桥接审计。")
        if not comparison:
            status, label = "unknown", "未生成跨层关联报告"
        elif comparison.get("system_edge_claim_allowed") is True and modes.get("session-and-tool", {}).get("accepted", 0) > 0:
            status, label = "accepted", "会话与精确工具 ID 关联成功"
        elif comparison.get("capture_status") == "incomplete":
            status, label = "incomplete", "系统采集或工具 ID 不完整"
        else:
            status, label = "abstain", "已有报告，关联证据不足"
        return dict(status=status, label=label, native_tools=native, system_tools=system, modes=modes,
                    process_bridge=bridge, scope=comparison.get("scope") or "尚无可核验报告。",
                    edge_claim_allowed=comparison.get("system_edge_claim_allowed"))

    def _trace(self, root):
        candidates = [root / "parsed/application-events.jsonl", root / "application-events.jsonl"]
        candidates += sorted(root.glob("*/parsed/application-events.jsonl"))
        candidates += sorted(root.rglob("alignment-session-and-tool/application-trace.jsonl"))
        candidates += sorted(root.glob("trace.jsonl"))
        path = next((p for p in candidates if p.is_file()), None)
        if not path:
            return []
        tool_names = {}
        for database in self._database_paths(root):
            try:
                with self._read_db(database) as db:
                    for tool_id, tool_name in db.execute("SELECT tool_call_id, tool_name FROM tool_calls LIMIT 1000"):
                        tool_names[tool_id] = tool_name
            except sqlite3.Error:
                continue
        rows = jsonl(path)
        ends = {}
        for row in rows:
            kind = row.get("event_type", "")
            if kind in {"tool.end", "session.end", "step.end"}:
                ends[(kind.split(".")[0], row.get("agent_id"), row.get("tool_call_id") or row.get("step_id") or row.get("session_id"))] = row
        result = []
        for index, row in enumerate(rows):
            kind = row.get("event_type", "")
            if kind not in {"tool.start", "session.start"}:
                continue
            identity = row.get("tool_call_id") or row.get("step_id") or row.get("session_id")
            end = ends.get((kind.split(".")[0], row.get("agent_id"), identity), {})
            start_ms = row.get("timestamp_ms")
            end_ms = end.get("timestamp_ms")
            duration = max(0, end_ms - start_ms) if isinstance(start_ms, (int, float)) and isinstance(end_ms, (int, float)) else None
            result.append(dict(id=row.get("event_id") or identity or str(index), name=("会话" if kind == "session.start" else row.get("tool_name") or tool_names.get(row.get("tool_call_id")) or "工具调用"),
                agent=row.get("agent_id") or "未知 Agent", start_ms=start_ms, duration_ms=duration,
                status="recorded" if end else "open", source=self._relative(path) + f"#line={index+1}",
                detail=scrub(dict(tool_call_id=row.get("tool_call_id"), session_id=row.get("session_id"), process=row.get("process"),
                    timestamp_semantics="本地原生流接收时间；不是工具原始执行时钟", evidence_kind=row.get("evidence_kind"), end_event=end.get("event_id")))))
        return result[:500]

    def _artifact_paths(self, root):
        allowed = []
        for path in root.rglob("*"):
            if not path.is_file() or not under(path, root) or path.suffix.lower() not in TEXT_SUFFIXES | IMAGE_SUFFIXES:
                continue
            relative = path.relative_to(root)
            if any(DENIED_NAME.search(part) for part in relative.parts) or "settings" in path.name.lower():
                continue
            if path.stat().st_size > 8 * 1024 * 1024:
                continue
            allowed.append(path)
        return sorted(allowed, key=lambda p: (len(p.relative_to(root).parts), p.as_posix()))

    def _artifacts(self, record):
        result = []
        for path in self._artifact_paths(Path(record["root"])):
            relative = path.relative_to(record["root"]).as_posix()
            identifier = hashlib.sha256(relative.encode()).hexdigest()[:16]
            result.append(dict(id=identifier, name=relative, kind="image" if path.suffix.lower() in IMAGE_SUFFIXES else "text",
                               url=f"/api/runs/{quote(record['id'])}/artifacts/{identifier}", path=self._relative(path)))
        return result

    def _generated_artifacts(self, record):
        return [dict(id="generated-" + suffix, name="平台按本次证据生成/" + name, kind=kind,
                     url=f"/api/runs/{quote(record['id'])}/artifacts/generated-{suffix}",
                     path="按本次运行 SQLite 和原始摘要实时生成", generated=True)
                for suffix, name, kind in (("chart", "evidence.svg", "image"), ("report", "evidence.md", "text"), ("json", "evidence.json", "text"))]

    def _source_artifacts(self, record):
        """Only a provenance-declared existing file inside this repository is eligible."""
        root = Path(record["root"])
        provenance = load(root / "dataset-provenance.json", {})
        source_ref = provenance.get("source_path") if isinstance(provenance, dict) else None
        if not source_ref or not isinstance(source_ref, str):
            return []
        candidates = [self.repo / source_ref, self.repo / "Reference paper/datasets" / source_ref]
        result = []
        for path in candidates:
            path = path.resolve()
            if not under(path, self.repo) or not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES or path.stat().st_size > 8 * 1024 * 1024:
                continue
            if any(DENIED_NAME.search(part) for part in path.relative_to(self.repo).parts):
                continue
            identifier = "original-" + hashlib.sha256(str(path).encode()).hexdigest()[:16]
            result.append(dict(id=identifier, name="原始数据/" + path.name, kind="text", path=self._relative(path),
                url=f"/api/runs/{quote(record['id'])}/artifacts/{identifier}", absolute=str(path)))
        return result[:1]

    def _http_evidence(self, root):
        successes, attempts, errors, records, measured = 0, 0, 0, 0, False
        codes, models, providers = {}, set(), set()
        for path in self._database_paths(root):
            try:
                with self._read_db(path) as db:
                    columns = {row[1] for row in db.execute("PRAGMA table_info(llm_calls)")}
                    if "status_code" not in columns:
                        continue
                    model_column = "model" if "model" in columns else "NULL"
                    provider_column = "provider" if "provider" in columns else "NULL"
                    values = db.execute(f"SELECT status_code, {model_column}, {provider_column}, COUNT(*) FROM llm_calls GROUP BY status_code, {model_column}, {provider_column}").fetchall()
                    measured = True
                    for code, model, provider, count in values:
                        records += count
                        if model:
                            models.add(str(model))
                        if provider:
                            providers.add(str(provider))
                        try:
                            code = int(code)
                        except (ValueError, TypeError):
                            continue
                        if 100 <= code <= 599:
                            attempts += count
                            codes[str(code)] = codes.get(str(code), 0) + count
                        if 200 <= code <= 299:
                            successes += count
                        elif 400 <= code <= 599:
                            errors += count
            except sqlite3.Error:
                continue
        return dict(http_successes=successes if measured else None, http_attempts=attempts if measured else None,
                    http_errors=errors if measured else None, http_status_counts=codes,
                    llm_records=records if measured else None, observed_models=sorted(models), observed_providers=sorted(providers))

    def _derived_report(self, detail):
        api, relation = detail["api"], detail["correlation"]
        show = lambda value: "未知" if value is None else str(value)
        rows = [f"# {detail['name']}\n", f"运行 ID：`{detail['id']}`", f"状态：{detail['status']}",
                f"输入：{detail['dataset'].get('source_path') or '未登记'}", "\n## API 与会话证据\n",
                f"{api['label']}。CLI 会话 {show(api['sessions'])}，成功 {show(api['successful_sessions'])}，CLI 自报 USD {show(api['cost_usd'])}。",
                f"数据库中 HTTP 请求记录：{show(api.get('http_attempts'))}；HTTP 2xx：{show(api['http_successes'])}；HTTP 错误：{show(api.get('http_errors'))}。{api['scope']}",
                "\n## 跨层关联\n", f"{relation['label']}。原生工具 {show(relation['native_tools'])}，系统工具 {show(relation['system_tools'])}。"]
        for mode, counts in relation["modes"].items():
            rows.append(f"- {mode}: accepted={show(counts['accepted'])}, abstain={show(counts['abstain'])}")
        bridge = relation["process_bridge"]
        rows += [f"\n受控 Bash 进程桥接：accepted={show(bridge['accepted'])}, abstain={show(bridge['abstain'])}。", relation['scope'],
                 "\n## SQLite 原始记录数\n", "| 表 | 行数 |", "|---|---:|"]
        rows += [f"| {name} | {show(value)} |" for name, value in detail['database']['counts'].items()]
        rows += ["\n## 来源\n", detail['root_path'],
                 "平台由现有工件生成此摘要；控制器生命周期不被当作应用 Trace；任务注入失败不等于平台执行失败。"]
        return "\n\n".join(rows)

    def _chart(self, detail):
        counts = [(name, count) for name, count in detail["database"]["counts"].items() if isinstance(count, int)]
        height = max(260, 130 + len(counts) * 42)
        top = [f'<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="{height}" viewBox="0 0 1000 {height}" role="img">',
               '<rect width="100%" height="100%" fill="#f8fafc"/>',
               '<g font-family="Segoe UI,Microsoft YaHei,sans-serif" fill="#172f49">',
               f'<text x="30" y="36" font-size="20">SQLite recorded rows · {escape(detail["id"])}</text>',
               '<text x="30" y="64" font-size="13">Generated from this run only. Counts are records, not causal accuracy.</text>']
        maximum = max([v for _, v in counts] or [1]) or 1
        for index, (name, value) in enumerate(counts):
            y = 95 + index * 42
            width = value / maximum * 600
            top += [f'<text x="30" y="{y+17}" font-size="14">{escape(name)}</text>',
                    f'<rect x="220" y="{y}" width="{width:.1f}" height="24" rx="5" fill="#17827f"/>',
                    f'<text x="{235+width:.1f}" y="{y+17}" font-size="14">{value}</text>']
        if not counts:
            top.append('<text x="30" y="125" font-size="16">No readable SQLite measurements for this run.</text>')
        return "\n".join(top + ["</g></svg>"])

    def _timeline_event(self, row):
        stage = row.get("stage") or row.get("event") or "recorded"
        at = row.get("at") or row.get("timestamp")
        semantics = "source timestamp"
        if not at and isinstance(row.get("wall_time_ns"), (int, float)):
            at = datetime.fromtimestamp(row["wall_time_ns"] / 1_000_000_000, timezone.utc).astimezone().isoformat(timespec="milliseconds")
            semantics = "observer wall_time_ns converted to timezone-aware ISO; monotonic_ns retained only as elapsed-clock provenance"
        elif not at and isinstance(row.get("timestamp_ms"), (int, float)):
            at = datetime.fromtimestamp(row["timestamp_ms"] / 1000, timezone.utc).astimezone().isoformat(timespec="milliseconds")
            semantics = "source timestamp_ms converted to timezone-aware ISO"
        labels = {
            "record_spawned": "系统采集器已启动", "record_ready": "系统采集器就绪",
            "debug_spawned": "语义观察器已启动", "capture_ready": "采集链路就绪",
            "agent_a_start": "Agent A 开始会话", "agent_a_finished": "Agent A 会话结束",
            "agent_b_start": "Agent B 开始会话", "agent_b_finished": "Agent B 会话结束",
            "stop_requested": "请求停止采集", "stopped": "采集已停止",
        }
        return dict(at=at, stage=stage, message=row.get("message") or row.get("detail") or labels.get(stage) or stage,
                    timestamp_semantics=semantics, wall_time_ns=row.get("wall_time_ns"), monotonic_ns=row.get("monotonic_ns"))

    def artifact(self, identifier, artifact_id):
        record = self.get_run(identifier)
        if not record:
            return None
        if artifact_id in {"generated-chart", "generated-report", "generated-json"}:
            detail = self.detail(identifier)
            if artifact_id == "generated-chart":
                return "image/svg+xml", self._chart(detail).encode("utf-8"), "evidence.svg"
            if artifact_id == "generated-report":
                return "text/plain; charset=utf-8", self._derived_report(detail).encode("utf-8"), "evidence.md"
            report = {k: detail[k] for k in ("id", "status", "api", "correlation", "database", "evidence_sources")}
            return "text/plain; charset=utf-8", json.dumps(report, ensure_ascii=False, indent=2).encode("utf-8"), "evidence.json"
        for original in self._source_artifacts(record):
            if original["id"] == artifact_id:
                return self._text_file(Path(original["absolute"]))
        for path in self._artifact_paths(Path(record["root"])):
            relative = path.relative_to(record["root"]).as_posix()
            if hashlib.sha256(relative.encode()).hexdigest()[:16] != artifact_id:
                continue
            if path.suffix.lower() in IMAGE_SUFFIXES:
                return mimetypes.guess_type(path.name)[0] or "application/octet-stream", path.read_bytes(), path.name
            return self._text_file(path)
        return None

    def _text_file(self, path):
        try:
            text = path.read_text(encoding="utf-8-sig")
            if path.suffix == ".json":
                text = json.dumps(scrub(json.loads(text)), ensure_ascii=False, indent=2)
            elif path.suffix == ".jsonl":
                lines = []
                for line in text.splitlines():
                    try:
                        lines.append(json.dumps(scrub(json.loads(line)), ensure_ascii=False))
                    except ValueError:
                        lines.append(scrub(line))
                text = "\n".join(lines)
            else:
                text = scrub(text)
            return "text/plain; charset=utf-8", text.encode("utf-8"), path.name
        except (OSError, UnicodeError, ValueError):
            return None

    def dataset_source(self, dataset_id):
        dataset = next((d for d in self.catalog() if d["id"] == dataset_id), None)
        if not dataset:
            return None
        path = (self.repo / dataset["source_path"]).resolve()
        if not under(path, self.repo) or not path.is_file() or path.stat().st_size > 16 * 1024 * 1024:
            return None
        return self._text_file(path)

    def detail(self, identifier):
        record = self.get_run(identifier)
        if not record:
            return None
        root = Path(record["root"])
        capture_path, capture = self._capture(root)
        comparison_path, comparison = self._comparisons(root)
        database = self._inventory(root)
        api = self._api(capture, record)
        http = self._http_evidence(root)
        api.update(http)
        api["models"] = sorted(set(api["models"]) | set(http["observed_models"]))
        if http["http_attempts"] and not http["http_successes"] and http["http_errors"]:
            api["status"] = "failed"
            if "401" in http["http_status_counts"]:
                api["label"] = "请求已捕获，HTTP 401 认证失败"
            elif "403" in http["http_status_counts"]:
                api["label"] = "请求已捕获，HTTP 403 访问被拒绝"
            else:
                codes = "、".join(code for code in http["http_status_counts"] if int(code) >= 400)
                api["label"] = "请求已捕获，HTTP " + codes + " 调用失败"
        elif http["http_successes"] and api["status"] == "unknown":
            api["status"], api["label"] = "partial", "HTTP 成功响应已捕获，CLI 会话摘要缺失"
        api["scope"] = "会话数来自 CLI 摘要，费用为 CLI 自报、非供应商最终账单；HTTP 成功数是 SQLite 中 HTTP 2xx 的 LLM 记录数，不去重推算外部计费请求。"
        correlation = self._correlation(comparison)
        if comparison_path:
            relations = jsonl(comparison_path.parent / "alignment-session-and-tool/application-alignments.jsonl", 200)
            correlation["links"] = [scrub({k: row.get(k) for k in ("agent_id", "session_id", "tool_call_id", "status", "reason", "target_ref", "session_system_pid")}) for row in relations]
            if correlation["process_bridge"]["accepted"] is None:
                controlled = load(comparison_path.parent / "controlled-instrumentation/controlled-instrumentation-report.json", {})
                counts = controlled.get("status_counts") or {}
                if counts:
                    correlation["process_bridge"].update(accepted=counts.get("accepted", 0), abstain=counts.get("abstain", 0), scope=controlled.get("boundary"))
        artifacts = self._artifacts(record)
        originals = self._source_artifacts(record)
        artifacts += [{k: v for k, v in original.items() if k != "absolute"} for original in originals]
        artifacts += self._generated_artifacts(record)
        traces = self._trace(root)
        dataset = next((d for d in self.catalog() if d["id"] == record.get("dataset_id")), None)
        if dataset is None:
            provenance = load(root / "dataset-provenance.json", {})
            dataset = dict(id=record.get("dataset_id"), name=record.get("dataset_name"), experiment_type="historical",
                description="历史运行输入。原始路径按已有 provenance 记录展示；未补造数据集。", input_kind="historical_unregistered",
                record_count=None, source_path=provenance.get("source_path"), source_url=None, api_required=None, available=None, budget_usd=None)
        # Public replay input is one frozen public-input.json, not the full catalog corpus.
        public_input = next((item for item in artifacts if item["name"] == "workspace/public-input.json"), None)
        if public_input:
            dataset = dict(dataset, input_kind="public_derived_replay", record_count=1,
                source_path=public_input["path"], source_url=public_input["url"], api_required=True, available=True,
                description="本次真实会话使用这一个冻结任务输入；源自公开样本，不代表重跑整个公开数据集。",
                original_source_path=originals[0]["path"] if originals else None,
                original_source_url=originals[0]["url"] if originals else None)
        timeline = record.get("timeline") or jsonl(root / "lifecycle.jsonl") or jsonl(root / "controller-lifecycle.jsonl") or jsonl(root / "observer-lifecycle.jsonl")
        timeline = [self._timeline_event(x) for x in timeline]
        report_paths = sorted(root.rglob("scenario-validation-report.json"))
        validation = load(report_paths[0], {}) if report_paths else {}
        outputs = []
        for artifact in artifacts:
            name = artifact["name"]
            if "/workspace/" in "/" + name and Path(name).suffix == ".json":
                value = load(root / name)
                outputs.append(dict(name=name, content=scrub(value), url=artifact["url"]))
        result = {key: record.get(key) for key in ("id", "name", "dataset_id", "dataset_name", "status", "created_at", "finished_at", "source_kind", "summary")}
        error = record.get("error")
        old_result = record.get("result") or {}
        if not error and record.get("status") == "failed":
            error = dict(stage=old_result.get("failed_stage") or record.get("stage"), message=old_result.get("note") or record.get("summary"), exit_code=old_result.get("exit_code"))
        items = [
            dict(name="输入可追溯", status="verified" if dataset.get("available") else "unknown", detail=dataset.get("source_path") or "未登记原始输入"),
            dict(name="真实 API / CLI", status="verified" if api["status"] == "confirmed" else api["status"], detail=api["label"]),
            dict(name="系统数据库", status="not_required" if api["status"] == "not_required" else "verified" if database["files"] else "unknown", detail="离线输入 SQLite，不是系统监控数据" if api["status"] == "not_required" else f"{len(database['files'])} 个 SQLite 工件"),
            dict(name="跨层工具关联", status="verified" if correlation["status"] == "accepted" else correlation["status"], detail=correlation["label"]),
        ]
        agent_costs = [dict(agent=a.get("agent_id") or "session", cost_usd=a.get("reported_cost_usd")) for a in capture.get("agents", [])]
        result.update(dataset=dataset, api=api, correlation=correlation, readiness=dict(items=items),
            database=database, artifacts=artifacts, timeline=scrub(timeline), traces=traces,
            charts=dict(table_counts=[dict(name=k, value=v) for k, v in database["counts"].items()], agent_costs=agent_costs,
                        tool_durations=[dict(name=t["agent"] + " · " + t["name"], value=t["duration_ms"]) for t in traces if t["detail"].get("tool_call_id")]),
            outputs=outputs, error=scrub(error), root_path=self._relative(root),
            validation=scrub(validation), evidence_sources=dict(capture=self._relative(capture_path) if capture_path else None,
                correlation=self._relative(comparison_path) if comparison_path else None),
            input_audit=scrub(load(root / "audit-report.json") or load(root / "input-audit.json")))
        return result
