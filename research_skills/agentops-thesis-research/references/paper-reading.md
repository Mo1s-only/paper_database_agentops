# Paper Reading Workflow

Use this when reading, summarizing, comparing, or critiquing individual papers.

## Intake

Record:

- paper title, year, venue if available;
- file path in this repository;
- reading purpose: background, baseline, method inspiration, failure taxonomy, monitoring/tracing, evaluation, or writing support;
- current status: first pass, deep read, comparison, or citation candidate.

## Reading Output

Produce notes in this structure:

1. `One-sentence contribution`: what the paper claims to add.
2. `Problem setting`: the system, agent, trace, failure, or monitoring scenario.
3. `Method core`: the mechanism, model, instrumentation, trace graph, attribution method, or evaluation design.
4. `Evidence`: datasets, experiments, metrics, case studies, ablations, or qualitative examples.
5. `Limitations`: explicit limitations and inferred weaknesses, labeled separately.
6. `Use for my thesis`: how it may support the user's AgentOps thesis.
7. `Claim-evidence rows`: short table mapping claims to page/section/table evidence when available.

## Critique Lens

For AgentOps and multi-agent failure papers, check:

- Does the paper observe runtime behavior, infer causality, or only summarize logs?
- What is the unit of analysis: agent, action, message, tool call, trace span, task, or system?
- Are failures categorized by root cause, symptom, location, time, or responsibility?
- Is there a reproducible benchmark or only case studies?
- Does the method support online monitoring, offline diagnosis, or both?
- What assumptions would break in real multi-agent systems?

## Output Discipline

- Do not overclaim a paper's relevance.
- State when a detail is not available in the PDF or extracted text.
- Preserve citation metadata exactly when visible.
- If the user asks for a note file, create a separate note rather than rewriting the original PDF-derived text.

