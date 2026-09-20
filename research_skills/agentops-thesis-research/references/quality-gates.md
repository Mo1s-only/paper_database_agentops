# Quality Gates

Use this before treating any research artifact as ready.

## Evidence Gate

Check:

- Are central claims supported by papers, notes, code, logs, or explicit user input?
- Are unsupported claims labeled `UNVERIFIED` or removed?
- Are inferred claims clearly marked as inference?
- Are contradictions surfaced rather than smoothed over?

## Citation Gate

Check:

- title, authors, year, venue, DOI/arXiv URL when available;
- citation actually supports the sentence where it appears;
- no fabricated bibliographic fields;
- no stale current information without verification.

## Thesis Argument Gate

Check:

- Does the artifact answer the current research question?
- Is the contribution distinct from related work?
- Are scope and limitations explicit?
- Is the evidence sufficient for the strength of the claim?

## Writing Gate

Check:

- one message per paragraph;
- stable terminology;
- no generic filler;
- transitions explain cause, contrast, consequence, or refinement;
- Chinese and English terms are consistent when both are used.

## Experiment Gate

Check:

- hypothesis, baseline, metric, data/task, and expected output are named;
- results are not claimed before they exist;
- logs, scripts, or notebooks are linked when used as evidence;
- failure cases are categorized consistently.

## Readiness Labels

Use:

- `READY`: all blocking evidence exists and consistency checks passed.
- `READY_WITH_WARNINGS`: usable, but limitations or missing metadata remain.
- `NOT_READY`: central claim, citation, result, or structure is still unsupported.

Always state the reason for the label.

