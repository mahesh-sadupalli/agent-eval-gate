"""Input/output contract for the agent eval gate (PROTOCOL.md v0.1, section 9).

The boundary between the M1 harness, which produces paired measurements, and
the M2 gate, which turns them into a release decision. Types plus validation
only: no statistics, no I/O.

Key facts encoded here:
  * Verified outcomes are binary (1 = the permitted call executed and matched
    the reference). A missing label is either hidden from this consumer or an
    invalid measurement with a recorded reason, never a silent 0.
  * Judge scores are per-arm probabilities of verified success in [0, 1].
    Invalid judge output is missing, not 0.
  * All deltas are candidate minus baseline.
  * Judge-based methods see calibration (C) labels and evaluation (U)
    predictions only. U labels live in a separate assessment artifact.
  * Tied cases (both-pass, both-fail) are conditional diagnostics. They do
    not identify the judge's error on untied cases.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum

PROTOCOL_VERSION = "bfcl-pilot-v0.1"


class Verdict(str, Enum):
    SHIP = "ship"
    NO_SHIP = "no_ship"
    UNRESOLVED = "unresolved"


class UnresolvedReason(str, Enum):
    INVALID_MEASUREMENT = "invalid_measurement"
    INSUFFICIENT_CALIBRATION = "insufficient_calibration"
    INSUFFICIENT_SAMPLES = "insufficient_samples"
    INTERVAL_CROSSES_THRESHOLD = "interval_crosses_threshold"


class Split(str, Enum):
    DEVELOPMENT = "development"
    CALIBRATION = "calibration"
    EVALUATION = "evaluation"


class Position(str, Enum):
    """Which arm the judge saw as response A.

    AB: baseline shown as A. BA: candidate shown as A. Balanced assignment
    is recorded so position effects can be reported; it does not guarantee
    they cancel.
    """
    AB = "AB"
    BA = "BA"


class MethodId(str, Enum):
    """Decision methods compared in M3 (PROTOCOL.md section 8)."""
    DIRECT_VERIFICATION = "direct_verification"
    RAW_JUDGE_THRESHOLD = "raw_judge_threshold"
    NAIVE_JUDGE_CI = "naive_judge_ci"
    RESIDUAL_CORRECTION = "residual_correction"


class Stratum(str, Enum):
    """Verified-outcome pattern of one paired case."""
    BOTH_PASS = "both_pass"
    BOTH_FAIL = "both_fail"
    CANDIDATE_ONLY_PASS = "candidate_only_pass"
    BASELINE_ONLY_PASS = "baseline_only_pass"


def _check_label(name: str, label: int | None, invalid_reason: str | None) -> None:
    if label is not None and label not in (0, 1):
        raise ValueError(f"{name} must be 0, 1, or None, got {label!r}")
    if label is not None and invalid_reason is not None:
        raise ValueError(f"{name} has a label and an invalid reason; pick one")


def _check_probability(name: str, p: float | None) -> None:
    if p is None:
        return
    if not math.isfinite(p) or not 0.0 <= p <= 1.0:
        raise ValueError(f"{name} must be a finite probability in [0, 1], got {p!r}")


@dataclass(frozen=True)
class VariantSpec:
    """One agent configuration. Pinned by snapshot and hashes, not aliases.

    Baseline and candidate may be identical: that is the wiring control.
    """
    model_snapshot: str          # dated snapshot, e.g. "gpt-4.1-mini-2025-04-14"
    prompt_hash: str
    tool_schema_hash: str
    temperature: float
    top_p: float
    max_output_tokens: int
    retrieval: str = "none"      # RAG enters in M4 as a variant, not a gate dependency


@dataclass(frozen=True)
class CaseResult:
    """One paired case: both arms' verified outcomes and judge scores."""
    case_id: str
    family_id: str
    split: Split
    run_id: str
    verifier_version: str
    judge_version: str           # judge snapshot + rubric id
    baseline_verified: int | None
    candidate_verified: int | None
    baseline_score: float | None     # judge P(verified success), baseline arm
    candidate_score: float | None    # judge P(verified success), candidate arm
    position: Position | None        # None if the judge was not run
    replicate: int = 0
    baseline_invalid_reason: str | None = None
    candidate_invalid_reason: str | None = None
    artifact_ref: str | None = None  # pointer to raw records under runs/

    def __post_init__(self) -> None:
        _check_label("baseline_verified", self.baseline_verified, self.baseline_invalid_reason)
        _check_label("candidate_verified", self.candidate_verified, self.candidate_invalid_reason)
        _check_probability("baseline_score", self.baseline_score)
        _check_probability("candidate_score", self.candidate_score)

    @property
    def is_measurement_invalid(self) -> bool:
        return (self.baseline_invalid_reason is not None
                or self.candidate_invalid_reason is not None)

    @property
    def verified_delta(self) -> int | None:
        """Candidate minus baseline verified outcome: -1, 0, 1, or None."""
        if self.baseline_verified is None or self.candidate_verified is None:
            return None
        return self.candidate_verified - self.baseline_verified

    @property
    def judge_delta(self) -> float | None:
        """Candidate minus baseline judge probability, or None if either is missing."""
        if self.baseline_score is None or self.candidate_score is None:
            return None
        return self.candidate_score - self.baseline_score

    @property
    def stratum(self) -> Stratum | None:
        b, c = self.baseline_verified, self.candidate_verified
        if b is None or c is None:
            return None
        if b == c:
            return Stratum.BOTH_PASS if b == 1 else Stratum.BOTH_FAIL
        return Stratum.CANDIDATE_ONLY_PASS if c == 1 else Stratum.BASELINE_ONLY_PASS

    @property
    def is_truth_tied(self) -> bool:
        """Both arms have the same valid verified outcome.

        The judge delta on these cases is a conditional discrepancy that still
        contains random error; it is not the bias on untied cases.
        """
        return self.stratum in (Stratum.BOTH_PASS, Stratum.BOTH_FAIL)


@dataclass(frozen=True)
class StratumDiagnostic:
    n_cases: int
    mean_judge_delta: float | None   # None when the stratum is empty
    mean_residual: float | None      # verified delta minus judge delta


@dataclass(frozen=True)
class CalibrationReport:
    """M1 diagnostic on the calibration split. Not consumed by the gate."""
    run_id: str
    judge_version: str
    sampling_design: str             # e.g. "simple random partition of 22 families"
    n_families: int
    n_cases: int
    n_invalid: int
    residual_mean: float | None      # family-weighted mean of D_f - J_f
    strata: dict[Stratum, StratumDiagnostic]


@dataclass(frozen=True)
class GateConfig:
    alpha: float = 0.05              # one fixed comparison; no multiplicity correction
    min_effect: float = 0.05         # delta, proportion scale (5 pp)
    method: MethodId = MethodId.RESIDUAL_CORRECTION

    def __post_init__(self) -> None:
        if not 0.0 < self.alpha < 1.0:
            raise ValueError(f"alpha must be in (0, 1), got {self.alpha!r}")
        if not -1.0 < self.min_effect < 1.0:
            raise ValueError(f"min_effect is a proportion in (-1, 1), got {self.min_effect!r}")


@dataclass(frozen=True)
class GateInput:
    """What a judge-based method may see: C labels, U predictions only."""
    baseline: VariantSpec
    candidate: VariantSpec
    calibration: list[CaseResult]
    evaluation: list[CaseResult]
    config: GateConfig = field(default_factory=GateConfig)
    protocol_version: str = PROTOCOL_VERSION

    def __post_init__(self) -> None:
        for c in self.calibration:
            if c.split is not Split.CALIBRATION:
                raise ValueError(f"{c.case_id}: split {c.split.value} in calibration set")
        for c in self.evaluation:
            if c.split is not Split.EVALUATION:
                raise ValueError(f"{c.case_id}: split {c.split.value} in evaluation set")
            if c.baseline_verified is not None or c.candidate_verified is not None:
                raise ValueError(f"{c.case_id}: evaluation labels must not reach the gate")
        cal_families = {c.family_id for c in self.calibration}
        overlap = cal_families & {c.family_id for c in self.evaluation}
        if overlap:
            raise ValueError(f"families in both splits: {sorted(overlap)}")


@dataclass(frozen=True)
class GateOutput:
    verdict: Verdict
    reason: UnresolvedReason | None  # set exactly when verdict is UNRESOLVED
    method: MethodId
    protocol_version: str
    estimate: float | None           # primary estimate, proportion scale
    interval: tuple[float, float] | None  # the one decision interval
    coverage_scope: str              # what the interval covers, in words
    components: dict[str, tuple[float, float]] = field(default_factory=dict)
    rationale: str = ""

    def __post_init__(self) -> None:
        if (self.verdict is Verdict.UNRESOLVED) != (self.reason is not None):
            raise ValueError("reason must be set exactly when verdict is unresolved")
        if self.interval is not None and self.interval[0] > self.interval[1]:
            raise ValueError(f"empty interval {self.interval!r}")
