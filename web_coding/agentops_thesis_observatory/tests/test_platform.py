"""Integration checks against the preserved research evidence and HTTP boundary."""
from __future__ import annotations

import json
from http.server import ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from backend.data import Repository
from backend.server import make_handler, platform_lock


class NoLaunchRunner:
    active_run = None

    def preflight(self, dataset_id):
        return {"ok": True, "checks": [], "api_required": False, "budget_usd": 0}


class ControllerSingleton(unittest.TestCase):
    def test_second_controller_cannot_recover_or_interrupt_another_controllers_runs(self):
        with TemporaryDirectory() as directory, patch("backend.server.SITE", Path(directory)):
            with platform_lock():
                with self.assertRaises(SystemExit):
                    with platform_lock():
                        self.fail("duplicate controller acquired the workspace lock")
            with platform_lock():
                pass


class PlatformIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = TemporaryDirectory()
        cls.repo = Repository(runtime_dir=Path(cls.temp.name) / "runtime")
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(cls.repo, NoLaunchRunner()))
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(2)
        cls.temp.cleanup()

    def read(self, path):
        with urlopen(self.base + path, timeout=30) as response:
            return json.load(response)

    def test_historical_success_is_exposed_as_its_own_run(self):
        rows = self.read("/api/runs")["runs"]
        self.assertIn("real-canary-20261022-45", [row["id"] for row in rows])
        run = self.read("/api/runs/real-canary-20261022-45")
        self.assertEqual(run["dataset_id"], "error-propagation-v1")
        self.assertEqual(run["api"]["sessions"], 2)
        self.assertEqual(run["api"]["successful_sessions"], 2)
        self.assertAlmostEqual(run["api"]["cost_usd"], 0.0496904)
        self.assertEqual(run["correlation"]["native_tools"], 4)
        self.assertEqual(run["correlation"]["system_tools"], 4)
        self.assertEqual(run["correlation"]["modes"]["session-and-tool"]["accepted"], 4)
        self.assertEqual(run["correlation"]["modes"]["process-and-tool"].get("accepted", 0), 0)
        self.assertEqual(run["database"]["counts"]["tool_calls"], 4)

    def test_real_dataset_definition_and_sqlite_rows_can_be_opened(self):
        catalog = self.read("/api/catalog")
        dataset = next(row for row in catalog["datasets"] if row["id"] == "error-propagation-v1")
        self.assertTrue(dataset["api_required"])
        with urlopen(self.base + dataset["source_url"], timeout=5) as response:
            self.assertIn("SCENARIOS", response.read().decode("utf-8"))
            self.assertIn("sandbox", response.headers["Content-Security-Policy"])
        run = self.read("/api/runs/real-canary-20261022-45")
        db_index = next(index for index, db in enumerate(run["database"]["files"])
                        if any(table["name"] == "tool_calls" for table in db["tables"]))
        table = self.read(f"/api/runs/real-canary-20261022-45/tables?db={db_index}&table=tool_calls")
        self.assertEqual(table["total"], 4)
        self.assertEqual(len(table["rows"]), 4)
        self.assertTrue(table["columns"])
        self.assertNotIn("request_body", table["columns"])

    def test_failed_attempt_does_not_borrow_successful_run_evidence(self):
        run = self.read("/api/runs/run-0522348ce0c6")
        self.assertEqual(run["status"], "failed")
        self.assertIsNone(run["api"]["sessions"])
        self.assertIsNone(run["api"]["cost_usd"])
        self.assertIsNone(run["correlation"]["native_tools"])
        self.assertEqual(run["correlation"]["status"], "unknown")

    def test_wrong_origin_and_traversal_are_rejected(self):
        request = Request(self.base + "/api/preflight", data=b'{"dataset_id":"error-propagation-v1"}',
                          headers={"Content-Type": "application/json", "X-Observatory-Control": "1",
                                   "Origin": "https://unrelated.example"})
        with self.assertRaises(HTTPError) as error:
            urlopen(request, timeout=5)
        self.assertEqual(error.exception.code, 403)
        with self.assertRaises(HTTPError) as error:
            urlopen(self.base + "/api/datasets/unknown/source", timeout=5)
        self.assertEqual(error.exception.code, 404)
        with self.assertRaises(HTTPError) as error:
            urlopen(self.base + "/api/runs/real-canary-20261022-45/artifacts/%2e%2e", timeout=5)
        self.assertEqual(error.exception.code, 404)


if __name__ == "__main__":
    unittest.main()
