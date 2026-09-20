# Discovery Grill Workflow

Use this when the user wants to be grilled, interviewed, pressure-tested, or helped to externalize thinking about the thesis.

This workflow is adapted from the user-recommended `grill-me` skill. Its purpose is extraction, not polished writing.

## When To Use

Use for:

- thesis direction decisions;
- experiment feasibility;
- advisor meeting preparation;
- defense question practice;
- choosing between contributions;
- converting vague ideas into concrete research questions.

Do not use when the user simply asks for a finished deliverable. Use the normal writing or research workflow instead.

## Capture Policy

For a substantive grill session, create a durable note before asking the first question:

```text
research_notes/YYYY-MM-DD-<topic>-grill.md
```

If `research_notes/` does not exist, create it. The note should contain:

- title;
- date;
- session goal;
- running summary;
- Q&A log;
- open flags.

After each user answer, update the file before asking the next question. The file is the source of truth if the conversation gets long.

## Interview Method

- Ask one question at a time.
- Include a recommended answer or best current guess with each question so the user can confirm, correct, or reject it quickly.
- Resolve upstream decisions before downstream details.
- If the answer can be found in this repository, inspect the files instead of asking.
- Capture uncertainty as an open flag with an owner or next evidence source.
- Continue until the user says enough or the major branches are covered.

## Question Shape

Use questions like:

- "My current guess is X. Is that correct, or should it be Y?"
- "What would make this direction fail?"
- "Which evidence would convince your advisor?"
- "What baseline would a skeptical reviewer expect?"
- "What part of this plan is currently hand-wavy?"
- "If you had two weeks, what result would be enough to keep this direction alive?"

## Session Close

At the end:

1. Reconcile the note for contradictions.
2. Update the summary and open flags.
3. Propose one next research action.
4. Ask whether any reusable insight should be promoted into `research_skills/`, a thesis plan, or a persistent note.

