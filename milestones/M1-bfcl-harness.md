# Milestone 1 — BFCL harness

**Filled plan · 2026-11-20 · implementation not yet performed.** Prerequisite: the [M0 answers](M0-measurement-protocol.md) and [PROTOCOL.md](../PROTOCOL.md). This milestone turns that specification into trustworthy paired measurements. M2 owns inference; M3 owns the final assessment; M4 introduces retrieval.

## Q1. What must exist before the first study run?

**Answer:** a versioned protocol, frozen case/family manifest, exact model and benchmark pins, implemented contract migration, and a passing development-only verifier preflight. Provider access is checked against the dated model IDs in protocol §3. If a pin is unavailable, amend it before collecting calibration/evaluation data.

Implement protocol §9's contract changes first, preserving unrelated working-tree edits. Resolve the existing `GROUND_TRUTH_TOL` import mismatch by aligning tests with binary verification. Do not import old sequential, BH, or tied-bound assumptions into the new harness.

**Done when:** the implementation refers to one protocol/configuration hash, binary-label and score validation works, and the contract tests cover the intended semantics.

**Evidence — 2026-11-20 (contract part only, written by Claude on request):** `src/agent_eval_gate/contract.py` migrated per protocol §9: `Verdict.UNRESOLVED` + `UnresolvedReason`; binary 0/1 labels with an invalid reason or hidden (None); judge scores validated as finite probabilities; `Stratum` (four outcome patterns); `GateConfig(alpha=0.05, min_effect=0.05, method)` without sequential/BH; `GateInput` rejects U labels, wrong splits, and family overlap; `GateOutput` requires a reason exactly when unresolved; `CalibrationReport` replaces `JudgeReliability`; `GROUND_TRUTH_TOL` removed. `tests/test_contract.py` rewritten: `uv run --extra dev pytest` → 28 passed. Still open in Q1: frozen manifest, protocol/config hash, model-availability preflight.

## Q2. Which benchmark data does the harness load?

**Answer:** load the pinned historical `exec_simple` files and exactly the 60 case IDs / 26 families in protocol §7. Copy that documentation table into a machine-readable manifest during implementation. Assert unique IDs, the expected split counts, and zero family overlap. Preserve upstream IDs and record source file checksums.

Load questions and tool schemas into agent requests. Keep reference calls, expected outputs, and verification labels in a verifier-only store. Record all eligibility exclusions before any generated outcomes. Do not replace this slice with current BFCL AST categories.

**Done when:** the inventory reproduces 12 development, 22 calibration, and 26 reserved evaluation cases; a manifest validation failure prevents a run.

**Evidence — 2026-11-24 (written by Claude on request):** `src/agent_eval_gate/bfcl.py` holds the §7 manifest, the pinned commit, and SHA-256 checksums of both source files; `scripts/fetch_bfcl.py` downloads them into the ignored `data/bfcl/<commit>/` and verifies (both `ok`). Loader checks: checksum, 100 unique source IDs, all 60 manifest IDs present, 4/10/12 families and 12/22/26 cases, no duplicate IDs, every selected reference `exact_match`. Agent data (`load_case_inputs`: question + schemas) and verifier data (`load_references`) load separately; a test confirms no reference call appears in agent inputs. Excluded: 40 IDs = 38 remote-service + `estimate_derivative` 24/25, matching §2. `uv run --extra dev pytest` → 39 passed.

## Q3. How will execution verification work?

**Answer:** implement a small adapter around the audited local function definitions and exact-result comparison, retaining upstream function bodies and local helpers. The upstream import-time API-key check must not force external-service access for this local slice. Record the extraction/adapter version and dependencies; this is an adapted historical BFCL harness.

Accept only a permitted function call with literal arguments. Do not execute unrestricted model-generated Python. Reject extra calls, unknown functions, executable expressions, and malformed arguments. Execute accepted calls in an isolated worker with a read-only function bundle, fresh argument objects, no network access, a 5-second tool timeout, and a recorded memory limit. The reference runs separately; a mutated input, such as `polygon_area`'s list append, cannot affect the other arm or the reference.

Compare the resulting value under the pinned exact-match semantics, including tuple-to-list conversion. A wrong agent call or agent-caused timeout is failure. A broken reference, unavailable dependency, worker crash unrelated to agent behavior, or adapter inconsistency is invalid measurement with a reason.

**Done when:** development fixtures show a known correct call passes, a changed result fails, invalid calls are rejected, references are stable on replay, and mutation cannot cross runs. No claim of general verifier correctness follows from these checks.

## Q4. How are baseline and candidate paired and isolated?

**Answer:** both arms receive the same question and tool schema, with the single prompt difference in protocol §3. Use separate provider requests without shared conversations, per-arm temporary directories and worker processes, copied inputs, and separate logs. Each case contributes one paired observation; record both arms even if one fails.

Use the prespecified arm execution-order schedule to reduce systematic time/order effects. State isolation does not imply independent outcomes: the shared task induces pairing, and related cases remain grouped by family. The smoke test with identical configurations checks wiring; two independent model calls need not return identical outputs.

**Done when:** an isolation check proves that an artifact or mutated value produced by one arm is unavailable to the other, and every record has an unambiguous baseline/candidate mapping.

## Q5. How is judge scoring randomized and blinded?

**Answer:** use the frozen probability-of-success prompt. Present anonymized A/B calls with the task and schema, excluding agent model names, arm names, verifier outputs, and reference answers. Use the protocol's balanced, family-local order schedule, independent of calibration/evaluation assignment. Save the mapping before scoring.

Parse exactly two finite probabilities in [0,1], then restore baseline/candidate identity. Do not coerce bad output to zero or substitute a hand-scored value. A swapped-order fixture must demonstrate that the recorded candidate-minus-baseline sign survives A/B reversal. Report order-stratified diagnostics without assuming randomization removes all judge error.

**Done when:** deterministic fixtures cover AB and BA mapping, missing/out-of-range scores, and the absence of hidden labels from serialized judge requests.

## Q6. What is recorded, and what can the gate see?

**Answer:** produce the following artifacts. Names below are planned artifact roles, not existing files or contract fields.

| Artifact | Required contents |
|---|---|
| Run manifest | Protocol/config hashes, project revision and dirty patch hash, BFCL/adapter versions, source checksums, case/family/split IDs, model IDs, prompt/schema hashes, request settings, seeds and actual order assignments, environment versions |
| Arm records | Request/response, parsed call, timing, token usage, provider request/model metadata, worker status, retry attempts, output artifact references |
| Judge records | Exact blinded input, raw output, parsed scores or validation error, A/B mapping, model/rubric identity, usage and latency |
| Verification store | Per-arm binary result or invalid reason, reference/checker version, execution outputs, error classification; access separated from agents/judges |
| Gate export | C labels and predictions, U predictions only, family weights, calibration provenance and validity metadata |
| Assessment export | Hidden U labels released only after method outputs freeze; combined with C to assess the full-pool target |
| Calibration report | Completion counts, both arm success rates, paired and family means, four outcome strata, position diagnostics, missingness, calls, cost and latency |

Save raw run data under the already-ignored `runs/` and benchmark material under `data/`. Publish a small scrubbed report/manifest when available; preserve the existing private-document boundary. Record retrieved-document IDs as empty for M1. Do not log API secrets. Checksums support replay and accidental-change detection, not proof against fabricated records.

**Done when:** the report can be traced to raw records, and the judge-method export contains no U verification labels.

## Q7. What happens on errors, retries, and interruptions?

**Answer:** set an agent/judge request timeout of 120 seconds and allow at most two transport retries, with 1-second and 2-second delays, for rate limits, network failures, and server errors. Save every attempt and count its cost. Provider responses indicating malformed model content are not transport failures and do not authorize answer-quality retries.

Resume only missing transport work under identical configuration, keyed by run/case/arm/attempt. Never overwrite accepted outputs or select the best attempt. Judge schema failure remains missing judgment; infrastructure failure remains invalid verification. Do not drop incomplete pairs from the denominator without reporting them. If required measurements remain unavailable, the run is incomplete and cannot supply a release decision.

A changed model, prompt, verifier, or manifest starts a new run ID. No extra cases or repeated generations are added in response to an unfavorable or unresolved result. A spending cap stops collection and records incompleteness; choose the actual cap before a paid run.

**Done when:** an interrupted fixture resumes without duplicate accepted observations; transport errors, agent failures, and verifier faults remain distinguishable.

## Q8. What runs in M1, and what remains held out?

**Answer:** first run development fixtures and the 12 development cases; then freeze the configuration and run the 22 calibration cases (10 families) once for the prompt comparison. Expected primary calls, excluding retries and development: 44 agent calls, 22 paired judge calls, and 44 arm verifications, plus separately counted reference executions.

This is an engineering/calibration demonstration, not the M3 inferential experiment. Leave the 26 evaluation cases unrun in M1. For M3, generate a fresh, interleaved, split-blind C+U batch under frozen settings before revealing its labels; do not combine old M1 calibration records with later U records and assume split-independent measurement. Calibration labels must not be used to tune the judge or variants for that same planned study. If development continues using C outcomes, declare that pool used for development and redesign the study before claiming held-out evidence.

Produce stratum diagnostics only where data exist. An empty both-fail stratum is reported as empty, not zero bias. Do not estimate a universal correction bound from tied cases or produce an M2 release verdict here.

**Done when:** one complete calibration run is inspectable, with actual counts and error accounting, and no evaluation labels have entered judge requests or tuning.

## Q9. What makes the run reproducible?

**Answer:** support two distinct workflows: a fresh generation run using the frozen manifest, and a replay of saved calls/judge responses through parsing, verification, aggregation, and reporting. Record the actual tested setup and commands in the completed run report. There is no usable harness command to document yet.

Replay must reproduce case selection, arm mapping, outcomes, and report aggregates under the pinned environment. A fresh hosted-model run may differ and receives a new run ID. Record dependency versions and the local-function adapter so importing a newer BFCL release cannot silently change results.

**Done when:** a clean environment reproduces the report from saved artifacts, and a second operator can follow the documented commands without hidden setup.

## Q10. Implementation order and exit checklist

Implement in this order: contract migration → manifest loader → local verifier and isolation → paired agent runner → blinded judge → durable records/resume → report/replay. Test each boundary with fixtures before paid model calls. Gate inference, RAG, MCP, sequential methods, and deployment are outside M1.

- [x] Contract and tests agree with the binary fixed-sample protocol. (2026-11-20, 28 tests)
- [x] Benchmark/source pins and the exact split inventory are validated. (2026-11-24)
- [ ] Development-only verifier, invalid-call, and isolation checks pass.
- [ ] Judge blinding and AB/BA mapping checks pass.
- [ ] One full calibration comparison is saved with missingness and cost accounted for.
- [ ] Replay reproduces recorded verification and aggregates.
- [ ] Actual commands, environment, evidence paths, and limitations are documented.
- [ ] Evaluation remains reserved; no performance, power, or gate-benefit claim exceeds the evidence.

**Current evidence:** protocol/source audit only. No checklist item is marked complete by writing this plan. The M1 completion report must replace planned artifacts with actual paths, commands, counts, and observed limitations.
