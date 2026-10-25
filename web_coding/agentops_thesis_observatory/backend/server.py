"""Local HTTP boundary for the experiment workspace."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import json
import logging
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import re
from urllib.parse import parse_qs, unquote, urlsplit

VERSION = "2.0"
PLATFORM = "agentops-observatory"
SITE = Path(__file__).resolve().parents[1]
WEB = SITE / "web"
IDENTIFIER = re.compile(r"^[A-Za-z0-9_-]{1,120}$")


@contextmanager
def platform_lock():
    """One controller per workspace, even when different ports are requested."""
    runtime = SITE / "runtime"
    runtime.mkdir(exist_ok=True)
    handle = (runtime / "server.lock").open("a+b")
    if handle.tell() == 0:
        handle.write(b"0")
        handle.flush()
    handle.seek(0)
    try:
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        handle.close()
        raise SystemExit("This workspace already has a running Observatory controller. Use Start-Observatory.ps1 to reuse it.")
    try:
        yield
    finally:
        handle.seek(0)
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        handle.close()


def make_handler(repository, runner):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            logging.info("%s %s", self.address_string(), fmt % args)

        def _allowed(self):
            port = self.server.server_port
            return self.headers.get("Host", "") in {f"127.0.0.1:{port}", f"localhost:{port}"}

        def _send(self, status, body, content_type="application/json; charset=utf-8", filename=None):
            if not isinstance(body, bytes):
                body = json.dumps(body, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "same-origin")
            if filename:
                self.send_header("Content-Disposition", 'inline; filename="' + re.sub(r"[^A-Za-z0-9_.-]", "_", filename) + '"')
                self.send_header("Content-Security-Policy", "default-src 'none'; sandbox")
            self.end_headers()
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def _error(self, status, message):
            return self._send(status, {"error": message})

        def do_GET(self):
            if not self._allowed():
                return self._error(403, "仅支持本机访问。")
            try:
                parsed = urlsplit(self.path)
                parts = [unquote(part) for part in parsed.path.strip("/").split("/") if part]
                if parts == ["api", "health"]:
                    return self._send(200, {"platform": PLATFORM, "version": VERSION,
                                            "workspace": str(SITE), "active_run": getattr(runner, "active_run", None)})
                if parts == ["api", "catalog"]:
                    datasets = repository.catalog()
                    names = {"cross_layer_live": "真实 API 跨层实验", "input_audit": "已有输入结构复核", "semantic_diagnosis": "语义诊断"}
                    types = [{"id": key, "name": names.get(key, key)} for key in names
                             if any(row["experiment_type"] == key for row in datasets)]
                    return self._send(200, {"datasets": datasets, "experiment_types": types})
                if parts == ["api", "runs"]:
                    return self._send(200, {"runs": repository.list_runs()})
                if len(parts) == 4 and parts[:2] == ["api", "datasets"] and parts[3] == "source":
                    value = repository.dataset_source(parts[2])
                    if not value:
                        return self._error(404, "登记的输入源文件不可用。")
                    mime, body, name = value
                    return self._send(200, body, mime, name)
                if len(parts) >= 3 and parts[:2] == ["api", "runs"] and IDENTIFIER.fullmatch(parts[2]):
                    run_id = parts[2]
                    if len(parts) == 3:
                        value = repository.detail(run_id)
                        return self._send(200, value) if value else self._error(404, "运行记录不存在。")
                    if len(parts) == 4 and parts[3] == "tables":
                        query = parse_qs(parsed.query)
                        try:
                            db_index = int(query.get("db", ["0"])[0])
                        except ValueError:
                            return self._error(400, "数据库编号无效。")
                        value = repository.database_preview(run_id, db_index, query.get("table", [""])[0])
                        return self._send(200, value) if value is not None else self._error(404, "数据表不可用。")
                    if len(parts) == 5 and parts[3] == "artifacts" and IDENTIFIER.fullmatch(parts[4]):
                        value = repository.artifact(run_id, parts[4])
                        if not value:
                            return self._error(404, "工件不存在或不支持预览。")
                        mime, body, name = value
                        return self._send(200, body, mime, name)
                if parts and parts[0] == "api":
                    return self._error(404, "接口不存在；请使用同一平台的启动地址。")
                assets = {"": ("index.html", "text/html; charset=utf-8"),
                          "index.html": ("index.html", "text/html; charset=utf-8"),
                          "app.js": ("app.js", "text/javascript; charset=utf-8"),
                          "styles.css": ("styles.css", "text/css; charset=utf-8")}
                asset = assets.get(parsed.path.strip("/"))
                if not asset:
                    return self._error(404, "页面不存在。")
                return self._send(200, (WEB / asset[0]).read_bytes(), asset[1])
            except Exception:
                logging.exception("GET request failed")
                return self._error(500, "本机数据读取失败，请查看 runtime/server-error.log。")

        def do_POST(self):
            port = self.server.server_port
            origins = {f"http://127.0.0.1:{port}", f"http://localhost:{port}"}
            if not self._allowed() or self.headers.get("Origin") not in origins | {None} or self.headers.get("X-Observatory-Control") != "1":
                return self._error(403, "请从本机平台页面发起操作。")
            if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                return self._error(415, "请提交 JSON。")
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 16_384:
                    return self._error(413, "请求大小无效。")
                payload = json.loads(self.rfile.read(length))
                if not isinstance(payload, dict):
                    raise ValueError("object required")
            except (ValueError, json.JSONDecodeError):
                return self._error(400, "JSON 请求无效。")
            try:
                parts = urlsplit(self.path).path.strip("/").split("/")
                if parts == ["api", "preflight"]:
                    return self._send(200, runner.preflight(str(payload.get("dataset_id", ""))))
                if parts == ["api", "runs"]:
                    code, result = runner.start(payload)
                    return self._send(code, result)
                if len(parts) == 4 and parts[:2] == ["api", "runs"] and parts[3] == "stop" and IDENTIFIER.fullmatch(parts[2]):
                    code, result = runner.stop(parts[2])
                    return self._send(code, result)
                if parts == ["api", "rescan"]:
                    repository.discover()
                    return self._send(200, {"runs": repository.list_runs()})
                return self._error(404, "操作不存在。")
            except Exception:
                logging.exception("POST request failed")
                return self._error(500, "操作失败，请查看本机控制器日志。")

    return Handler


def main():
    from backend.data import Repository
    from backend.runner import Runner
    parser = argparse.ArgumentParser(description="AgentOps experiment workspace")
    parser.add_argument("--port", type=int, default=8780)
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error("port must be 1024–65535")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    with platform_lock():
        repository = Repository()
        runner = Runner(repository)
        server = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(repository, runner))
        server.daemon_threads = True
        print(f"Observatory {VERSION}: http://127.0.0.1:{args.port}/", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()


if __name__ == "__main__":
    main()
