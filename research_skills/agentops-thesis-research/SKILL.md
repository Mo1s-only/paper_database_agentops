---
name: agentops-thesis-research
description: Use for all research work in this thesis repository: paper reading, literature review, AgentOps topic framing, experiment planning, thesis writing, citation checks, and research-quality review. Do not use for unrelated coding tasks unless they affect the thesis evidence base.
---

# AgentOps Thesis Research

This repository is the working base for a graduation thesis on AgentOps, multi-agent system monitoring, tracing, and failure attribution. Treat every research artifact as part of a traceable thesis argument, not as isolated notes.

## Core Rules

1. Never invent papers, citations, DOI values, experimental results, metrics, advisor comments, or thesis requirements.
2. Separate `VERIFIED`, `INFERRED`, `UNVERIFIED`, and `AUTHOR_INPUT_NEEDED`.
3. Preserve the user's intended research direction before improving wording or structure.
4. Map important claims to evidence from PDFs, extracted text, notes, code, or clearly identified external sources.
5. Prefer small, durable research outputs: evidence tables, gap maps, argument maps, chapter outlines, experiment plans, and quality gates.
6. Follow `git_skills.md` before committing or pushing.

## Route The Task

Read only the reference needed for the current request:

| Request type | Reference |
|---|---|
| Read, summarize, compare, or critique a paper | `references/paper-reading.md` |
| Build a literature review, related work, source map, or research gap table | `references/literature-review.md` |
| Frame the thesis topic, research question, contribution, or experiment plan | `references/topic-and-experiment-framing.md` |
| Draft or revise thesis chapters, abstracts, introductions, methods, related work, or conclusions | `references/thesis-writing.md` |
| Audit claims, citations, figures, consistency, or readiness | `references/quality-gates.md` |

For broad requests like "help me advance the thesis", start with `topic-and-experiment-framing.md`, then use the other references only as needed.

## Default Workflow

1. Identify the intended artifact: note, table, chapter text, plan, code change, or review.
2. Locate the evidence already in this repository before asking for new material.
3. Build a compact claim-evidence map:
   - `C#`: claim;
   - `E#`: evidence;
   - `R#`: reference/source;
   - `Gap#`: missing or weak evidence.
4. Produce the requested output.
5. End with the next useful research gate: missing source, experiment to run, section to draft, or decision to make.

## Repository Conventions

- Existing Chinese notes are valuable primary working artifacts; do not overwrite them unless explicitly asked.
- New durable research notes should use clear Chinese filenames unless the artifact is code-facing.
- For major synthesis artifacts, prefer Markdown tables that can later become thesis text.
- For experimental code or external repositories, keep provenance clear: upstream URL, commit if known, local changes, and what evidence the code supports.
- When using cloned GitHub research-skill sources, treat them as inspiration only. The authoritative local workflow is this skill.

