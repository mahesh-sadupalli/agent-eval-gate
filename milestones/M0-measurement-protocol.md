# Milestone 0 — Measurement protocol

**Filled 2026-11-20:** proposed answers for review and study preparation. The consolidated specification is [PROTOCOL.md](../PROTOCOL.md). Source inspection and planning calculations are complete; execution preflight and experimental results are not. These answers do not certify personal mastery or a completed experiment.

Decide what is measured and how a release decision is made, before writing harness code. Each answer becomes a section of `PROTOCOL.md`. Sources: `PROJECT_DIRECTION.md` §2–§6 and §8; the BFCL methodology post; the PPI paper (arXiv 2301.09633).

---

## Q1. Outcome
**State the primary outcome and its unit.**
- Proposed: change in execution-verified task-success rate (percentage points), candidate minus baseline.
- What counts as one "success" on a BFCL case? What exactly does the chosen checker verify (structure only, or the executed result)?

**Done when:** one sentence defines the outcome, and one sentence names what the verifier does *not* check.

**Proposed answer**

The primary outcome is candidate-minus-baseline change in execution-verified success, in percentage points, averaged within each family and then equally across study families. A case succeeds only when one permitted call executes and its result matches the pinned reference using BFCL's exact-result comparison. This verifies that concrete input/output check, not general semantics, subjective quality, or real-world safety. Invalid infrastructure is missing measurement, not failure. See [protocol §1](../PROTOCOL.md#1-question-outcome-and-scope) for the finite-pool target and secondary case-weighted rate.

---

## Q2. BFCL subset and version
**Choose and pin the benchmark slice.**
- Which BFCL revision (commit / release) and which categories? Do executable categories still exist in the current release, or do you need an older pinned one?
- How many cases are available, and how are they grouped into task families (the sampling unit)?

**Done when:** a revision ID, a list of categories, a case count, and a definition of "task family" are written down.

**Proposed answer**

Pin Gorilla commit `4d05b53fce8a2055957311817f6c7f9143acdc11`, immediately before executable-category retirement. Use only the historical `exec_simple` category: source inspection counted 100 cases, of which 60 local exact-match cases are selected across 30 functions and 26 families. Exclude 38 remote-service cases and 2 derivative cases that evaluate a code string. Families group a function's cases and merge shared helper dependencies. The exact ID/family/split table is in [protocol §7](../PROTOCOL.md#7-split-manifest-and-freeze); source links and verifier caveats are in [§2](../PROTOCOL.md#2-benchmark-pin-and-eligibility). These are inventory counts, not runtime results.

---

## Q3. Judge target and rubric
**What does the judge score, and is it on the same scale as Q1?**
- The judge predicts verified success (pass probability or pass/fail), not clarity or helpfulness.
- Judge model + version pin, prompt, how both arms are shown, and how AB/BA order is randomized.

**Done when:** the judge prompt is drafted and you can explain why equal pass/fail outcomes say nothing about subjective quality.

**Proposed answer**

The judge returns a separate probability of verified success for each arm, on [0,1]; their difference is candidate minus baseline. Proposed judge: `gpt-4.1-2025-04-14`; both agents: `gpt-4.1-mini-2025-04-14`. Use dated snapshots, temperature 0, recorded request settings, and the full prompt in [protocol §3](../PROTOCOL.md#3-agents-judge-and-rubric). These models require an availability/deprecation check before running. Blind arm/model identity and reference labels. Randomize balanced AB/BA presentation independently of split roles; preserve the actual mapping. Equal pass/fail outcomes do not establish equal clarity or helpfulness, so those qualities are outside the rubric.

---

## Q4. Role of truth-tied cases vs. representative labels
**Decide what tied cases are used for, and what supplies the calibration.**
- Tied cases (both-pass, both-fail): a conditional diagnostic, reported per stratum.
- A random verified calibration sample (PPI-style correction) as the baseline calibration method. Which assumptions does it need, and do they hold here?
- Can tied-only evidence support any release bound? If not, say what the gate does instead.

**Done when:** you can state, in your own words, why the mean judge delta on tied cases is not automatically the bias on untied cases.

**Proposed answer**

Use both-pass and both-fail cases as separate conditional diagnostics. Use all 10 randomly allocated calibration families for a representative residual correction, not a selected tied subset. For family means, residual = verified delta minus judge delta. A frozen judge, valid labels, split-independent measurement, and the prespecified sampling design are required. Ties alone do not identify errors on untied cases; tied-only calibration produces unresolved / insufficient_calibration. [Protocol §4–5](../PROTOCOL.md#4-calibration-and-tied-diagnostics) defines the PPI-inspired estimator and a finite-population interval rather than assuming independent-sample PPI guarantees.

---

## Q5. Release threshold and decision rule
**Fix the minimum worthwhile improvement and the three outcomes.**
- Threshold δ in percentage points, and why that value.
- Ship: whole interval > δ. No ship: whole interval ≤ δ. Unresolved: crosses δ, or measurements invalid, with a reason (insufficient samples / insufficient calibration / invalid measurement).
- Which interval (sampling + calibration uncertainty), and what coverage claim it carries.

**Done when:** the rule is written as pseudo-code and the status names are chosen.

**Proposed answer**

Choose δ = 5 percentage points as an explicit research policy threshold, not an established business threshold. Use a 95% design-based bounded-mean interval for the finite study pool, combining prediction-mean sampling uncertainty with calibration-residual uncertainty. The interval and its conditions are fully specified in [protocol §5](../PROTOCOL.md#5-estimator-interval-and-release-policy).

```text
invalid measurements -> unresolved / invalid_measurement
no representative calibration -> unresolved / insufficient_calibration
missing planned records -> unresolved / insufficient_samples
lower endpoint > 0.05 -> ship
upper endpoint <= 0.05 -> no_ship
otherwise -> unresolved / interval_crosses_threshold
```

Endpoints are proportions internally. The pilot's interval may be uninformative; that is not permission to drop an uncertainty component.

---

## Q6. Sample size and stopping
**Choose n in advance.**
- Power calculation for a paired difference in success rate at δ (state the assumed discordance rate).
- Rule: an unresolved result does not extend the same study.

**Done when:** n per comparison and the assumptions behind it are written down.

**Proposed answer**

Fix one paired run per selected case: 12 development cases (4 families), 22 calibration cases (10 families), and 26 evaluation cases (12 families). The primary study pool excludes development. At the release boundary itself, 80% power is not an appropriate target. For an alternative +10 pp versus a +5 pp threshold, an illustrative paired normal calculation with discordance 0.20 requires 613 independent cases; discordance 0.10/0.30 gives 299/927. This calculation does not cover clustering or calibration uncertainty and does not power the small BFCL pilot. [Protocol §6](../PROTOCOL.md#6-sample-size-stopping-and-feasibility) supplies the formula and stopping rule. No sample extension after an unresolved result; a later study needs a new frozen design.

---

## Q7. Splits and leakage
**Separate calibration from final evaluation.**
- Split by task family; which split the judge calibration sees; hidden labels never reach judge-based methods.
- What gets frozen before looking at final-evaluation labels (variants, rubric, calibration, policy).

**Done when:** a split table (family → split) is defined and the freeze list is written.

**Proposed answer**

Use the explicit family allocation in [protocol §7](../PROTOCOL.md#7-split-manifest-and-freeze), generated with seed 20261120. Development is for tuning; calibration labels estimate the residual after the rubric freezes; evaluation labels are visible only to the assessor after method outputs are saved. Freeze variants, models, prompts, adapter, case IDs, family weights, seeds, order, error/retry rules, sample sizes, correction, threshold, interval, and scenarios. Judge requests and later retrieval indexes exclude answer keys and hidden outcomes. Public reference source was inspected for this protocol; runtime blinding does not establish absence of pretraining contamination.

---

## Q8. Evaluation scenarios for the gate
**List the comparisons M3 will run.**
- Correctness-preserving presentation change (true delta ≈ 0), correctness-improving change, correctness-damaging change, and the real RAG variant.
- Metrics: false-release rate, power, missed improvements, abstention, coverage where the true effect is known, verification calls, judge calls, cost.

**Done when:** each scenario has an expected true effect and the metric list is fixed.

**Proposed answer**

M3 compares direct verification, a raw judge threshold, a naive judge-only interval, and representative-label correction. Include verified correctness-preserving presentation changes (zero effect), controlled +2 pp / +10 pp and −10 pp simulations, the actual prompt comparison (unknown effect), and later the real RAG comparison (unknown effect). Report false releases, power, no-ship missed improvements, abstention by reason, total non-release on improvements, coverage/width, absolute arm success, calls, tokens, retries, latency, and cost. Repeated simulations estimate rates with Monte Carlo uncertainty; one BFCL run gives one decision. See [protocol §8](../PROTOCOL.md#8-m3-scenarios-baselines-and-reporting).

---

## Q9. Contract revision
**Translate Q1–Q8 into the contract.**
- Which fields in `src/agent_eval_gate/contract.py` change (e.g. `Verdict.NEED_MORE_N` → unresolved with reason; `GateConfig.sequential`/BH defaults; `JudgeReliability` fields)?
- Known defect to resolve here: `tests/test_contract.py` imports `GROUND_TRUTH_TOL`, which the current `contract.py` does not define.

**Done when:** a field-by-field change list exists; the code change itself starts M1.

**Proposed answer**

The field-by-field migration is in [protocol §9](../PROTOCOL.md#9-planned-contract-revision-m1-work-no-schema-changed-here). Replace NEED_MORE_N with unresolved plus reason; use fixed-sample alpha 0.05 and min_effect 0.05; remove unsupported sequential/BH and tied-bound semantics; enforce binary verified outcomes; add family/split/run/provenance and validity metadata; separate hidden evaluation labels from judge-method inputs; and record one justified decision interval with its scope. Replace the generic reliability bound with representative residual evidence and separate tied diagnostics. Resolve the undefined GROUND_TRUTH_TOL test import by updating tests for the agreed binary target during M1, not by preserving obsolete graded-label semantics. No source or test changes are made in M0.

---

## Q10. Wrap-up
**3–5 lines: what is settled, what stays an assumption, and the first thing M1 needs.**

**Proposed wrap-up**

The outcome, historical BFCL slice, family split, scoring rubric, threshold, and fixed-sample policy are specified in PROTOCOL.md.
Representative labels supply calibration; truth ties remain conditional diagnostics.
The small pilot checks measurement and engineering feasibility, with no claim of adequate power or benefit over direct verification.
Verifier compatibility, provider access, and isolation remain execution checks; M1 begins there and implements the documented contract migration.
