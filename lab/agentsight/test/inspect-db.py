#!/usr/bin/env python3
"""Dump table names and row counts from an AgentSight session DB.

AgentSight ships no sqlite3 CLI dependency, so this uses the stdlib only.
"""
import sqlite3
import sys
from pathlib import Path

db = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).parent / "out" / "session.db")
if not db.exists():
    sys.exit(f"no database at {db}")

con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
tables = [
    r[0]
    for r in con.execute(
        "select name from sqlite_master where type='table' order by name"
    )
]
if not tables:
    sys.exit(f"{db} has no tables")

width = max(len(t) for t in tables)
total = 0
for t in tables:
    n = con.execute(f'select count(*) from "{t}"').fetchone()[0]
    total += n
    print(f"  {t:<{width}}  {n:>6}" + ("   <- has data" if n else ""))

print(f"\n{len(tables)} tables, {total} rows total in {db}")
