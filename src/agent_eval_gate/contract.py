"""Frozen input/output contract for the agent eval gate.

Interface-first: this file is the fixed boundary between the harness that
produces measurements and the gate that consumes them. Freezing it before
either is built is what lets them be built independently. TYPES ONLY --
no statistics, no I/O.

Key design facts encoded here:

  * CaseResult carries BOTH arms' ground truth. That is what makes the
    truth-tied differential-bias estimator computable: on cases where both
    arms share a verifiable outcome the true quality delta is zero, so any
    judge delta there is pure instrument bias.

  * PRECONDITION -- the judge rubric scoring *_score MUST target the SOFT
    axis (helpfulness, clarity, explanation quality), while *_ground_truth
    carries the HARD axis (AST match, tests pass). If the judge merely
    re-scores the hard axis, both arms land at the same score on every
    truth-tied case, judge_delta is ~0 everywhere, and the estimator is
    silently empty -- a null result that reads like a clean bill of health.

  * agreement_vs_truth is for CONTINUOUS judge scores (ICC / Spearman /
    Krippendorff alpha) -- never Cohen's kappa, which is categorical.

  * VariantSpec pins one shared variant matrix so baseline/candidate pairs
    stay comparable across every stage of the pipeline.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Verdict(str, Enum):
    SHIP = "ship"
    NO_SHIP = "no_ship"
    NEED_MORE_N = "need_more_n"


class Position(str, Enum):
    """Order the two arms were shown to the judge.

    The harness MUST balance AB and BA within each comparison so that position
    bias averages out to noise (killed by n) rather than leaking into the delta.
    """
    AB = "AB"
    BA = "BA"


#: Ground truth must be a DISCRETE outcome level (0.0/1.0, or graded bands).
#: Continuous partial credit -- e.g. SWE-bench fraction-of-tests-passing --
#: must be banded BEFORE it enters CaseResult. Otherwise exact-equality tie
#: detection almost never fires, the truth-tied set silently collapses toward
#: empty, SE -> inf, and the gate returns need_more_n with no error raised.
GROUND_TRUTH_TOL = 1e-9


@dataclass(frozen=True)
class VariantSpec:
    """One point in the shared variant matrix.

    A baseline/candidate pair should differ on exactly ONE axis so the measured
    delta is attributable to that change. Reused across all milestones.
    """
    model: str            # e.g. "claude-sonnet", "gpt-x", "gemini-y"
    prompt_variant: str   # e.g. "v0_baseline", "v1_terse"
    temperature: float


@dataclass
class CaseResult:
    """One paired evaluation on a single case: both arms, both judge scores,
    and BOTH arms' verifiable outcomes."""
    case_id: str
    domain: str                            # "bfcl", "swe_bench_verified", ...
    baseline_score: float                  # judge score, baseline arm
    candidate_score: float                 # judge score, candidate arm
    judge_version: str                     # pin; drift detection keys on this
    position: Position                     # randomized order actually used
    baseline_ground_truth: float | None    # verifiable outcome, baseline arm
    candidate_ground_truth: float | None   # verifiable outcome, candidate arm

    @property
    def judge_delta(self) -> float:
        """Candidate minus baseline, in judge-score units (still biased)."""
        return self.candidate_score - self.baseline_score

    @property
    def is_truth_tied(self) -> bool:
        """Both arms share the same verifiable outcome -> true per-case delta is
        0, so judge_delta on these cases is pure differential bias.

        Requires discrete ground-truth levels; see GROUND_TRUTH_TOL.
        """
        if self.baseline_ground_truth is None or self.candidate_ground_truth is None:
            return False
        return abs(self.baseline_ground_truth
                   - self.candidate_ground_truth) < GROUND_TRUTH_TOL


@dataclass
class JudgeReliability:
    """Per-domain instrument report produced by M1.

    The load-bearing numbers are the signed differential-bias estimate and its
    conservative bound; agreement_vs_truth is diagnostic.
    """
    domain: str
    agreement_vs_truth: float              # ICC / Spearman / Krippendorff alpha
    differential_bias_signed: float        # b_hat: mean judge_delta on truth-tied
    differential_bias_bound: float         # B: upper confidence limit on |b_hat|
    n_gold: int                            # total gold cases
    n_truth_tied: int                      # cases the estimate is built on


@dataclass
class GateConfig:
    alpha: float = 0.05                    # corrected across cases (Benjamini-Hochberg)
    sequential: bool = True                # always-valid p-values (mSPRT) if streaming
    min_effect: float = 0.0               # smallest delta worth shipping, on the
                                          # BIAS-CORRECTED scale, not raw
                                          # judge units (those are biased)
    use_signed_correction: bool = True    # True: center-correct by b_hat.
                                          # False: partial-identification bound only.


@dataclass
class GateInput:
    baseline: VariantSpec
    candidate: VariantSpec
    cases: list[CaseResult]
    reliability: list[JudgeReliability]    # one per domain present in cases
    config: GateConfig = field(default_factory=GateConfig)


@dataclass
class GateOutput:
    verdict: Verdict
    delta_obs: float                          # raw paired judge difference
    delta_corrected: float                    # delta_obs - b_hat (signed correction)
    identified_interval: tuple[float, float]  # [low, high], carries differential bias
    sampling_ci: tuple[float, float]          # noise-only interval (shrinks with n)
    dominant_term: str                        # "noise" | "differential_bias" | "effect"
    rationale: str                            # human-readable why
