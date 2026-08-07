# agent-eval-gate

**A ship/no-ship decision for LLM agents that accounts for the bias of the judge measuring them.**

> **Status: early development.** The interface contract is frozen and tested. The
> harness and the gate itself are being built against it. Not yet usable.

---

## The problem

You changed an agent — a new prompt, a cheaper model, an extra tool — and you need to know whether it got better. Since the output is open-ended, the standard answer is to have another LLM grade it, then compare averages.

That makes the judge a measuring instrument, and measuring instruments have two kinds of error:

- **Noise** is random. Collect more samples and it averages out.
- **Bias** is systematic. Collect more samples and it *does not* average out — the confidence interval just tightens around the wrong number.

LLM judges have well-documented systematic biases: they prefer longer answers, they favour whichever response is shown first, they rate their own model family more highly, and they change under you when the vendor updates the endpoint.

The scale of the problem is easy to understand. A real improvement between two agent versions is typically **2–3%**. A judge disagrees with ground truth on the order of **20%** of the time. The instrument's error is an order of magnitude larger than the effect being measured, and an unknown share of it is systematic.

Existing tools report a score. A score computed this way, presented with a confidence interval, is a **wrong answer with a p-value attached** — which is more dangerous than an obviously uncertain one, because it survives review.

## The approach

**1. Cancel what you can by design.** Evaluate both versions on the same cases with the same pinned judge, and randomise which order the judge sees them in. Any bias hitting both arms equally then drops out of the difference, and position bias degrades into noise that averaging removes. This is free and removes most of the danger.

**2. Measure what survives.** What remains is *differential* bias — bias that favours one version specifically, such as verbosity bias when the new version happens to produce longer answers. This does not cancel, and it is the only part that genuinely threatens the decision.

Measuring it normally requires human labels. It doesn't have to. Run on tasks whose outcome is objectively checkable by execution — the function call is correct or it isn't, the tests pass or they don't — and then look only at cases where **both versions produced the same verifiable outcome**. On those, the true quality difference is zero by construction, so whatever difference the judge reports there is *pure instrument bias*. No annotation required, at any scale you like.

**3. Carry it into the decision.** The measured bias corrects the estimate and widens the reported interval, so the verdict is only as confident as the instrument deserves.

### What that looks like

```
Raw judge result                     candidate is +3.0% better

On truth-tied cases                        +2.8%     <- true difference here
  (both arms, same verifiable outcome)                  is exactly zero, so
                                                        this is all bias

Corrected effect      3.0% - 2.8%  =       +0.2%
Sampling noise                             ±0.9%

VERDICT: no_ship
  Nearly all of the apparent gain is judge bias. The corrected effect is
  smaller than the noise; there is no evidence of a real improvement.
```

Because ground truth is verifiable, a verdict like this can be *checked*, not merely asserted.

## Design principles

**Bias is not noise.** They require opposite responses and are never combined. Widening an interval by an agreement statistic is not conservative — it is undefined, because the same agreement number can arise from pure noise (which more data fixes) or a systematic offset (which it never does).

**The judge rubric must not restate ground truth.** Ground truth scores the *hard* axis — correctness. The judge must score the *soft* axis — clarity, reasoning, helpfulness. If the judge merely re-checks correctness, both arms score identically on every truth-tied case and the bias estimate is silently empty: a null result that reads like a clean bill of health.

**Good experimental design beats correction after the fact.** Pairing and order-randomisation remove more bias, more cheaply, than any statistics applied downstream.

**Know where validation stops.** Verifiable tasks validate a judge precisely where a judge is least needed. Whether reliability measured there transfers to the unverifiable tasks judges actually exist for is an open question this project states rather than hides.

## Install

```bash
pip install -e ".[dev]"
pytest
```

Requires Python 3.10+. The contract has no dependencies; the statistics layer will need `numpy` and `scipy` (`pip install -e ".[stats]"`).

## The contract

The interface between the harness that produces measurements and the gate that consumes them is frozen first, so the two can be built independently. It is types only — no statistics, no I/O.

```python
from agent_eval_gate import CaseResult, Position

case = CaseResult(
    case_id="bfcl-0042",
    domain="bfcl",
    baseline_score=0.62,          # judge score, soft axis
    candidate_score=0.71,
    judge_version="judge-2026-08-01",
    position=Position.AB,         # randomised per comparison
    baseline_ground_truth=1.0,    # verifiable outcome, hard axis
    candidate_ground_truth=1.0,
)

case.judge_delta      # +0.09  — what the judge claims
case.is_truth_tied    # True   — but the true difference is zero,
                      #          so that +0.09 is pure judge bias
```

## Roadmap

| | | |
|---|---|---|
| **Contract** | frozen, tested | ✅ |
| **Harness** | run both arms on a verifiable-outcome benchmark; estimate differential bias, stratified by outcome and controlled for position | in progress |
| **Gate** | paired analysis, variance reduction, sequential testing, multiplicity correction, partial-identification intervals | next |
| **Distilled judge** | small local judge matched against the gold set; report the agreement-vs-cost curve | planned |
| **Demo** | one command: an apparent +3% gain rejected, with ground truth confirming | planned |

Starting on function-calling benchmarks, which are cheap to run — no containers, no agent loop. Container-based coding benchmarks follow once the pipeline works end to end.
