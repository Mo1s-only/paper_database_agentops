"""Verify every indexed run is readable and every SQLite run has a renderable chart."""
import argparse
import json
from urllib.parse import quote
from urllib.request import urlopen


def read(base, path):
    with urlopen(base + path, timeout=30) as response:
        return json.load(response)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:8780")
    args = parser.parse_args()
    runs = read(args.base, "/api/runs")["runs"]
    databases = charts = tables = 0
    errors = []
    for run in runs:
        identifier = quote(run["id"], safe="")
        try:
            detail = read(args.base, f"/api/runs/{identifier}")
            files = detail["database"]["files"]
            if not files:
                continue
            databases += 1
            with urlopen(args.base + f"/api/runs/{identifier}/artifacts/generated-chart", timeout=15) as response:
                assert response.headers["Content-Type"].startswith("image/svg+xml")
                assert b"<svg" in response.read()
            charts += 1
            for index, database in enumerate(files):
                for table in database["tables"]:
                    if table.get("rows") is None:
                        continue
                    preview = read(args.base, f"/api/runs/{identifier}/tables?db={index}&table=" + quote(table["name"]))
                    assert preview["total"] == table["rows"], table["name"]
                    tables += 1
        except Exception as error:
            errors.append({"id": run["id"], "error": str(error)})
    print(json.dumps(dict(runs=len(runs), sqlite_runs=databases, charts=charts, tables=tables, errors=errors), ensure_ascii=False))
    raise SystemExit(bool(errors))


if __name__ == "__main__":
    main()
