# Milestone roadmap — Agent Eval Gate

Started 2026-11-20. MLP style: one milestone at a time, guided docs in `milestones/`. Stages follow `PROJECT_DIRECTION.md` §4; that file stays the planning record where the two differ.

| # | Milestone | What it solves | Key deliverable |
|---|---|---|---|
| [M0](milestones/M0-measurement-protocol.md) | Measurement protocol | Settle the open decisions from `PROJECT_DIRECTION.md` §8 before any code: outcome, judge target, BFCL subset, release threshold, sample size, splits, decision statuses. | [PROTOCOL.md](PROTOCOL.md) (preregistration-style) + planned contract revision; code changes start M1 |
| [M1](milestones/M1-bfcl-harness.md) | BFCL harness | Run baseline and candidate agents on the same pinned executable BFCL cases with isolated state; record verification outcome, judge scores (randomized order), and provenance. | Harness + one reproducible paired run on the calibration split |
| M2 | Initial gate | One comparison, paired, fixed sample size; interval that carries sampling + calibration uncertainty; ship / no-ship / unresolved with the reason. | Gate function on the revised contract + simulation checks (null, regression, improvement) |
| M3 | Evaluation of the gate | Compare direct verification, raw judge threshold, naive judge CI, and calibrated methods on held-out tasks. | Report: false releases, power, missed improvements, abstention, cost |
| M4 | First real variant: RAG | Baseline vs. the same agent with embedding retrieval over tool documentation; does retrieval improve verified success? | One command → decision + evidence report |
| — | Later (only if M3 justifies) | SWE-bench, sequential inference, CUPED, multiple comparisons, MCP, small-judge distillation. | — |

Link to the AML project: its M5 (AI Eval) reuses the M2 gate to compare attack vs. defense conditions.

## Current documentation status — 2026-11-20

M0 has filled proposed answers and a consolidated protocol; M1 has a filled implementation guide and acceptance checklist. Neither an experiment nor the harness is complete. The proposed historical BFCL pilot contains 60 local exact-match cases in 26 families, with 12 development, 22 calibration, and 26 evaluation cases. It is a feasibility pilot, not a powered demonstration of fewer false releases. M1's calibration demonstration is separate from M3's fresh, split-blind assessment batch.

## Definition of done per milestone
Every question answered in my own words, each claim backed by a measurement from my own run (or a citation for M0), claims kept within `PROJECT_DIRECTION.md` §7, defensible without notes.
