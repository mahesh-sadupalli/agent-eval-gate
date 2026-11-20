# Project working instructions

## Current phase

Project started 2026-11-20. Read `PROJECT_DIRECTION.md`, then `MILESTONES.md`. M0 (measurement protocol, `milestones/M0-measurement-protocol.md`) is documentation only; implementation begins at M1 once M0 is answered.

Do not change source code, tests, dependencies, contract fields, or runtime behavior as part of a planning update. Preserve pre-existing working-tree edits. Known defects may be recorded for later; do not fix them merely because they are encountered during discussion.

## Direction

- Keep the bias-aware release gate as the central project.
- Treat fewer false releases as a hypothesis; report power, missed improvements, abstention, and cost alongside benefits.
- Define the outcome before choosing a correction. Equal verified outcomes do not establish equal subjective quality.
- Treat truth-tied discrepancies as conditional diagnostics. Transfer to other cases, domains, rubrics, and judge versions requires evidence.
- Start with a reproducible BFCL executable-case experiment and fixed-sample paired analysis. Runs need isolation; paired outcomes can be correlated.
- Keep RAG as the first planned variant. MCP, distillation, SWE-bench, sequential inference, CUPED, and multiple comparisons remain later options.
- Do not claim methods, commands, or results exist before they do.

## Reading and precedence

`PROJECT_DIRECTION.md` is the current planning record; `README.md` summarizes it. Local `DESIGN.md`, `PRIMER.md`, and diagrams contain earlier drafts and are historical where they conflict with the current direction. `CLAUDE.md` points to these same instructions.

The actual interface path is `src/agent_eval_gate/contract.py`. The existing draft does not establish that the statistical design is settled. Local design, primer, job-posting corpus, and diagrams are currently gitignored; preserve that publication boundary unless the user changes it.
