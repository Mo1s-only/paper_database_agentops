# Research Skill Sources

This directory is a local reference cache for cloned GitHub research-skill repositories. The cloned repositories are intentionally ignored by Git because they contain their own `.git` folders, examples, assets, scripts, and external histories.

Sources evaluated on 2026-09-20:

| Rank | Repository | Usefulness for this thesis workspace | Decision |
|---:|---|---|---|
| 1 | `https://github.com/cLin-c/paper-skill` | Broadest Chinese-first academic workflow: paper reading, literature review, manuscript planning, citation integrity, quality gates, and publication-style verification. | Adapted as the main evidence and quality-gate philosophy. |
| 2 | `https://github.com/AlveeeRahman/research-hound` | Strong five-stage scientific workflow with useful offline scripts and explicit separation of critical thinking, literature review, brainstorming, writing, and evaluation. | Adapted as the staged research pipeline. |
| 3 | `https://github.com/msimchowitz/writing-skills` | High-quality paper-writing and literature-review patterns, especially claim-led writing and section architecture. | Adapted for thesis chapter drafting and revision. |
| 4 | `https://github.com/Slazee/research-paper-writing-skills` | Practical ML/CV/NLP paper-section checklists, paragraph flow, and adversarial reviewer perspective. | Adapted for AI/AgentOps-style chapter writing. |
| 5 | `https://github.com/pinshuai/literature-review-skill` | Useful systematic-review process and citation verification ideas, but includes environment-specific tooling assumptions. | Used selectively for search logging and PRISMA-style review discipline. |

User-recommended additions:

| Repository | Usefulness for this thesis workspace | Decision |
|---|---|---|
| `https://github.com/blader/humanizer` | Strong final prose-polish workflow for removing generic AI-sounding patterns while preserving factual content. | Added as a final writing pass only after evidence and citations are stable. |
| `https://github.com/gusinov/grill-me` | Useful interview method for extracting implicit assumptions, decisions, and thesis constraints into durable notes. | Added for topic framing, experiment planning, advisor-meeting prep, and defense-question practice. |
| `https://github.com/Slazee/research-paper-writing-skills` | Already evaluated above; especially useful for section-specific AI/ML paper structure and skeptical reviewer self-review. | Promoted to a first-class writing workflow reference. |

Local policy:

- Keep this directory as reference material only.
- Do not commit cloned source repositories into the thesis repository.
- Put durable, thesis-specific workflows under `research_skills/`.
- If a source repository is re-cloned or updated, re-evaluate before changing the curated local skill.
