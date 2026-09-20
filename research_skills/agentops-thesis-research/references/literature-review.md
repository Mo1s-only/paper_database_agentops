# Literature Review Workflow

Use this for related work, research maps, source ledgers, and gap analysis.

## Review Contract

Before broad synthesis, define:

- review question;
- intended thesis chapter or section;
- retrieval cutoff date;
- inclusion and exclusion rules;
- comparison axes;
- minimum evidence needed before drawing conclusions.

For this thesis, useful comparison axes are:

- monitoring vs tracing vs observability vs failure attribution;
- single-agent vs multi-agent systems;
- runtime instrumentation vs post-hoc analysis;
- symptom detection vs root-cause attribution;
- trace granularity: message, tool call, span, agent, workflow, task;
- benchmark/evaluation type;
- intervention: alerting, debugging, repair, rollback, or optimization.

## Evidence Base

Maintain a table with at least:

| ID | Paper | Year | Problem | Method | Evidence | Limitation | Thesis use | Status |
|---|---|---:|---|---|---|---|---|---|

Use status labels:

- `core`: must cite;
- `supporting`: useful context;
- `contrast`: differs from or challenges the thesis direction;
- `candidate`: needs deeper reading;
- `exclude`: not directly useful, with reason.

## Synthesis Rules

- Organize by technical distinction, not by one-paper-per-paragraph summaries.
- Every synthesis paragraph should make one comparison claim and name the evidence base.
- State gaps as specific missing capabilities, not generic "more research is needed".
- Keep chronological history only when inheritance or field evolution matters.
- Use "reported", "suggests", "inferred", and "not disclosed" carefully.

## Search And Citation Hygiene

- Log search terms, databases, date, and retained count when doing new search.
- Prefer papers, official repositories, project pages, and appendices over secondary summaries.
- Verify bibliographic metadata before final thesis citation.
- For current or uncertain metadata, browse or use primary sources rather than relying on memory.

