# Agent Eval Gate — Project Goals and Direction

**Updated:** 2026-11-20  
**Phase:** discussion and documentation only. Implementation is not authorized by this planning update.

This is the current planning record. It supersedes conflicting methodology and roadmaps in the earlier design and primer. Existing code remains a prior interface draft; this document does not freeze or change the API.

## 1. Goal and research hypothesis

Build an open-source release-decision gate for two versions of an LLM agent. Investigate whether accounting for differential judge bias improves decisions on verifiable-outcome benchmarks, with explicit uncertainty and a quantified cost in power, missed improvements, abstention, and evaluation expense.

**Hypothesis to test, not an achieved result:** on specified tasks and agent changes, a paired, position-randomized comparison with appropriately measured bias correction can reduce false releases compared with a raw judge threshold and a naive judge-only confidence interval.

Define a false release against a prespecified outcome and minimum worthwhile improvement. Report missed improvements and unresolved decisions alongside false releases. Lowering false releases by never shipping is not success by itself. Do not promise a universal reduction in total decision error or a particular numerical reversal.

The gate remains the central project. RAG and MCP are variants it evaluates, not separate platforms. Validation on one benchmark does not establish production-wide reliability.

## 2. Measurement design to settle before coding

The recommended first target is the **change in execution-verified task-success rate**, in percentage points. The judge would estimate that same outcome on a compatible scale. The exact verifier and rubric remain discussion items.

If a judge scores clarity, helpfulness, or explanation quality instead, equal pass/fail outcomes do not establish equal quality on those dimensions. Correctness labels cannot alone validate or debias subjective quality. That track would require its own reference evidence.

On a truth-tied case, the verified-outcome difference is zero. A judge difference still contains random error. With aligned scoring targets, averaging these differences estimates a discrepancy **conditional on being tied**, not automatically the bias on all cases.

Keep both-pass and both-fail diagnostics separate. Test calibration on held-out untied cases and other strata. Error patterns occurring only when verified outcomes differ require additional verified examples or explicit transfer assumptions.

Do not describe the estimator as recovering an "orthogonal component" without a mathematical model defining and establishing that projection. Correctness-related error can appear within tied strata; its behavior outside them is not identified by ties alone.

## 3. Why include a judge?

Use direct verification for correctness decisions when it is trustworthy, available, and affordable. BFCL initially provides a controlled environment for testing judge-based decisions against an independent reference.

A possible later use is reducing costly verification: judge predictions for many cases plus a representative verified calibration sample. Measure the total cost; cheap BFCL checks may already be preferable.

Include a representative-label correction such as [prediction-powered inference](https://arxiv.org/abs/2301.09633) as a research baseline where its sampling and prediction-independence assumptions apply. Those guarantees do not automatically apply to a selected tied subset or distribution shift. The project has not established novelty or economic benefit.

## 4. Proposed implementation direction — future work

| Stage | Planned work | Evidence needed before expanding |
|---|---|---|
| Measurement protocol | Set outcome, rubric, practical release threshold, sampling unit, calibration strategy, and evaluation split | A coherent target and falsifiable experiment |
| M1: BFCL harness | Run paired baseline/candidate cases with isolated state and randomized judge order; record verification and provenance | Reproducible executable-case measurements; separate calibration and final evaluation tasks |
| M2: initial gate | One comparison, paired analysis, fixed sample size; account for sampling and calibration uncertainty | Checked behavior under null, regression, and improvement scenarios |
| M3: evaluation demo | Compare direct verification, raw judge threshold, naive judge CI, and calibrated methods | Held-out false releases, power, missed improvements, abstention, and cost |
| First real variant | Baseline versus RAG using embeddings and vector retrieval of tool documentation | Retrieved context is traceable; measure verified task success |
| Later extensions | SWE-bench, sequential inference, CUPED, multiple comparisons, MCP, small-judge distillation | Add each only when the initial experiment and measured benefit justify it |

BFCL includes AST and executable categories. Pin its revision, select an executable subset, and inspect the verifier: some checks establish structure rather than full semantic correctness. Claim only what the selected check verifies. See [BFCL methodology](https://gorilla.cs.berkeley.edu/blogs/8_berkeley_function_calling_leaderboard.html).

Pair tasks while preventing cross-arm communication, leaked context, and mutable shared state. Outcomes may be correlated because the task is shared; paired inference uses that dependence. Choose the task or task family as the sampling unit and account for repeated-run dependence.

The future evidence record should include agent/model/prompt versions, benchmark and judge versions, judge order, retrieved document IDs, tool calls, verification outcomes, calibration provenance, sample counts, cost, and latency. Keep answer keys and hidden evaluation outcomes out of the retrieval index. Logging improves traceability but does not prove authenticity.

## 5. Proposed decision behavior

Prespecify the minimum worthwhile improvement. For a justified decision interval on the same outcome scale:

- **Ship:** the entire interval exceeds the threshold.
- **No ship:** the entire interval is at or below the threshold under the chosen policy.
- **Unresolved:** the interval crosses the threshold, or the measurements do not support a decision; explain why.

Distinguish insufficient sampling, insufficient calibration, and invalid measurements. More samples cannot repair an unsupported transfer assumption. Exact status names and contract fields remain discussion items; no schema change is made here.

An interval like `[observed delta - B, observed delta + B]` is a sensitivity or identification interval if `B` is a defensible bias bound. It is not automatically a confidence interval. A release interval also requires sampling uncertainty and, when estimated, calibration uncertainty with justified joint coverage. Signed correction and residual bias bounds need explicit, distinct assumptions.

For the first fixed-sample study, select the sample size in advance. An unresolved result does not authorize repeatedly extending the same ordinary-CI experiment until significance. Plan a new study or adopt a validated sequential procedure.

CUPED needs informative covariates unaffected by the variant and a compatible estimator. Sequential methods need stopping-valid inference. BH addresses false-discovery rate for a defined family under its assumptions, not automatically the chance of any bad release. Their combination needs a joint argument and measured benefit. See [Always Valid Inference](https://arxiv.org/abs/1512.04922).

## 6. Evaluation of the gate itself

Freeze variants, rubrics, calibration procedures, and decision policies before inspecting final evaluation labels. Split at a task or task-family level that prevents leakage. Judge-based methods must not receive the hidden labels used to assess their decisions.

Include controlled presentation changes that preserve correctness and separate changes that improve or damage correctness. Also evaluate actual agent changes, starting with retrieval. Do not select only comparisons where correction looks favorable.

Report false-release rates for null/regression or below-threshold changes, power for above-threshold improvements, missed improvements, abstention, interval coverage where a reference effect is known, verification calls, judge calls, and total cost. Report uncertainty in these metrics and distinguish finite-benchmark findings from population claims. No useful advantage is a valid research outcome.

## 7. Claims and limits

This gate does not establish better evaluation in general, judge validity on subjective tasks, absolute agent capability, or general safety. Relative improvement does not establish that either agent meets an absolute quality standard.

- **Calibration coverage:** tied-subset evidence alone does not identify whole-population bias. Unknown coverage is a reason to withhold a calibrated decision, not invent a finite confidence bound.
- **Domain and version dependence:** a BFCL correction does not automatically transfer to SWE-bench, another judge, another rubric, or another agent change.
- **Verifier validity:** checkers can be incomplete, wrong, gamed, or corrupted. Verification is neither assumed free nor assumed infallible.
- **Record integrity:** statistical correction cannot authenticate fabricated or altered trajectories or `CaseResult` records.
- **Run isolation:** interference and leaked state can invalidate the intended comparison. Basic isolation and provenance belong in the future harness; adversarial integrity guarantees are outside the initial gate.
- **Shared blind spots:** equal additive errors cancel in a difference and may hide poor absolute performance. Shared model family does not prove equal errors; errors can affect the two arms differently, and different model families can share blind spots.

METR's [August 26, 2026 investigation](https://metr.org/blog/2026-08-26-openai-hugging-face-incident-investigation/) documents unauthorized communication between runs intended to be isolated, scorer-gaming work, and successful small-scale transcript spoofing. It describes attempts to substitute modified targets but does not establish successful substitution. This motivates the integrity boundaries; it neither validates our estimator nor demonstrates that this gate would detect such incidents.

## 8. Agreed direction and open decisions

**Retain:** the release gate, BFCL-first experiment, paired measurements, judge-bias diagnostics, explicit power/cost reporting, and RAG as the first agent variant. MCP remains a conditional harness-side stretch. Distillation and SWE-bench follow the initial experiment.

**Resolve before implementation:** the precise outcome and rubric; whether tied-only evidence can support any release bound; the role of representative verified labels; the release threshold and sample design; evaluation without label leakage; and decision/status fields.

**Immediate deliverable:** an agreed experimental protocol and accurate claims and limits. The later engineering deliverable is a reproducible command and report for baseline versus retrieval. Neither the harness nor that command exists yet.

**2026-11-20 planning update:** [PROTOCOL.md](PROTOCOL.md) now supplies proposed answers, with the completed [M0 worksheet](milestones/M0-measurement-protocol.md) and [M1 implementation guide](milestones/M1-bfcl-harness.md). The proposal uses a historical BFCL executable revision, 60 local exact-match cases grouped into 26 families, a family-weighted finite-pool outcome, representative calibration, and a conservative fixed-sample interval at a 5-percentage-point release threshold. The small pilot establishes no power or economic advantage; M1 must still validate the adapted verifier and model access. No source, test, dependency, or contract change is part of this update, and no experiment has run.
