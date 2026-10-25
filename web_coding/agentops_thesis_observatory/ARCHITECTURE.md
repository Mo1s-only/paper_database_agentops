# Observatory 2 — implementation contract

Local-only Python 3 standard-library server and buildless browser client. No hosted deployment.

## Ownership

- `backend/data.py`: catalog, historical discovery, registry, evidence, safe artifacts/SQLite previews.
- `backend/runner.py`: fixed WSL/offline runners, preflight, unique repeated runs, durable lifecycle.
- `backend/server.py`, `server.py`, launcher, integration tests: HTTP and orchestration.
- `web/index.html`, `web/app.js`, `web/styles.css`: Chinese UI.

## Data API

`Repository(runtime_dir=None, run_root=None, repo=None, discover=True)` in `backend.data`.

- `catalog()` returns dataset array.
- `list_runs()` returns run summary array.
- `get_run(id)` returns internal record including `root` absolute path, or None.
- `detail(id)` returns public detail below, or None.
- `new_run(name, dataset_id)` creates unique `run-*` under `lab/experiment/observatory_runs/`, returns internal record.
- `update(id, **changes)` persists fields; `event(id, stage, message, **extra)` appends timestamped lifecycle event.
- `discover()` refreshes historical index without altering source artifacts.
- `database_preview(id, db_index, table)` returns `{columns, rows, total, truncated}`.
- `artifact(id, artifact_id)` and `dataset_source(dataset_id)` return `(content_type, bytes, filename)` or None.

Dataset fields: `id,name,experiment_type,description,input_kind,record_count,source_path,source_url,api_required,available,budget_usd`.
Types: `cross_layer_live`, `input_audit`, `semantic_diagnosis` (only if implemented).
Catalog includes real `error-propagation-v1`, `routing-error-v1`, plus existing public normalized inputs and synthetic fixture audit. Input source links point to real files, not invented datasets.

Run summary: `id,name,dataset_id,dataset_name,status,created_at,source_kind,summary`.
Statuses: `queued,running,completed,partial,failed,interrupted,stopped`.

Public detail fields:

```
id,name,dataset_id,dataset_name,status,created_at,finished_at,source_kind,summary,
dataset:{...catalog entry},
api:{status,label,sessions,successful_sessions,cost_usd,http_successes,models,scope},
correlation:{status,label,native_tools,system_tools,modes:{mode:{accepted,abstain}},process_bridge:{accepted,abstain},scope},
readiness:{items:[{name,status,detail}]},
database:{files:[{id,name,path,tables:[{name,rows}]}],counts:{table:rows}},
artifacts:[{id,name,kind,url,path}],
timeline:[{at,stage,message}], traces:[{id,name,agent,start_ms,duration_ms,status,source,detail}],
charts:{}, outputs:[{name,content,url}], error:{stage,message,exit_code}, root_path
```

Unknown metrics must be null, not zero. Imported run45 (2026-10-22 error propagation) has 2 successful CLI sessions, native/system tool IDs 4/4, session-and-tool accepted 4/4. General process-and-tool remains abstain; controlled Bash bridge must be labeled separately. Do not infer causality from network counts or semantic joins.

## Runner API

`Runner(repository)` in `backend.runner`; `.preflight(dataset_id)` -> `{ok,checks:[{name,ok,detail}],api_required,budget_usd}`; `.start(payload)` -> `(HTTP status, response)`; `.stop(id)` -> same.

Start payload: `{name,dataset_id,experiment_type,confirm_api}`. Only catalogued fixed commands. Record invocation metadata and safe actionable failure even before capture starts. No secrets in API or process output. Repeated experiments always use a new ID. One active live run at a time. Per-session CLI soft cap defaults $0.05. Reuse run45's known source-built AgentSight binary and `--tool-id-bridge`; verify CLI arguments and execute offline postprocessing to generate alignment reports. No forced AgentRx stage after a cross-layer experiment.

## HTTP contract

- GET `/api/health` -> `{platform:"agentops-observatory",version:"2.0",active_run,...}`
- GET `/api/catalog` -> `{datasets:[...],experiment_types:[{id,name}]}`
- GET `/api/runs` -> `{runs:[...]}`
- GET `/api/runs/<id>` -> public detail
- GET `/api/runs/<id>/tables?db=0&table=tool_calls` -> preview
- GET `/api/runs/<id>/artifacts/<artifact_id>` -> safe file
- GET `/api/datasets/<id>/source` -> source text
- POST `/api/preflight` payload `{dataset_id}` -> preflight
- POST `/api/runs` -> created run `{id,...}`
- POST `/api/runs/<id>/stop`
- POST `/api/rescan` -> `{runs:[...]}`

JSON POST requires same-origin and `X-Observatory-Control: 1`; loopback only. No CORS, file traversal, raw credential/stdout streams. Use JSON errors `{error:"readable message"}`.

Client polls active run every 2 seconds. Hash routes `#runs`, `#new`, `#run/<id>/<overview|traces|data|files>`. Default select run45 success if available, otherwise most recent. A prominent run header shows exact ID, dataset, date and historical/current source. New run form chooses name, type, input; shows real source and API cost, runs preflight, and launches with explicit API confirmation. Clear why start is disabled. Avoid project metrics and unrelated research prose in per-run views.
