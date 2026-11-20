"""Contract tests for the binary, fixed-sample protocol (PROTOCOL.md v0.1).

Replaces the earlier graded-outcome tests: labels are now 0/1, missing labels
carry a reason or are hidden, and judge scores are probabilities.
"""
import math

import pytest

from agent_eval_gate.contract import (
    CaseResult,
    GateConfig,
    GateInput,
    GateOutput,
    MethodId,
    Position,
    Split,
    Stratum,
    UnresolvedReason,
    VariantSpec,
    Verdict,
)


def case(base=1, cand=1, b_score=0.5, c_score=0.5, split=Split.CALIBRATION,
         family="f1", case_id="exec_simple_0", **kw):
    return CaseResult(
        case_id=case_id, family_id=family, split=split, run_id="run-0",
        verifier_version="v0", judge_version="judge-v0",
        baseline_verified=base, candidate_verified=cand,
        baseline_score=b_score, candidate_score=c_score,
        position=Position.AB, **kw,
    )


SPEC = VariantSpec("gpt-4.1-mini-2025-04-14", "p0", "s0", 0.0, 1.0, 2048)


# --- deltas and strata ---------------------------------------------------

def test_deltas_are_candidate_minus_baseline():
    c = case(base=0, cand=1, b_score=0.2, c_score=0.9)
    assert c.verified_delta == 1
    assert c.judge_delta == pytest.approx(0.7)


@pytest.mark.parametrize("base,cand,stratum,tied", [
    (1, 1, Stratum.BOTH_PASS, True),
    (0, 0, Stratum.BOTH_FAIL, True),
    (0, 1, Stratum.CANDIDATE_ONLY_PASS, False),
    (1, 0, Stratum.BASELINE_ONLY_PASS, False),
])
def test_strata(base, cand, stratum, tied):
    c = case(base=base, cand=cand)
    assert c.stratum is stratum
    assert c.is_truth_tied is tied


def test_missing_label_has_no_delta_and_is_not_tied():
    """Unknown outcome is not a zero delta."""
    c = case(base=None, cand=1)
    assert c.verified_delta is None
    assert c.stratum is None
    assert not c.is_truth_tied


def test_missing_judge_score_has_no_judge_delta():
    assert case(c_score=None).judge_delta is None


# --- validation ----------------------------------------------------------

@pytest.mark.parametrize("bad", [0.5, 2, -1, True + 1])
def test_non_binary_label_rejected(bad):
    with pytest.raises(ValueError):
        case(base=bad)


def test_label_and_invalid_reason_are_exclusive():
    with pytest.raises(ValueError):
        case(base=1, baseline_invalid_reason="worker_crash")


def test_invalid_measurement_is_flagged_not_failed():
    c = case(base=None, baseline_invalid_reason="reference_broken")
    assert c.is_measurement_invalid
    assert c.verified_delta is None


@pytest.mark.parametrize("bad", [-0.01, 1.01, math.nan, math.inf])
def test_judge_score_must_be_probability(bad):
    with pytest.raises(ValueError):
        case(b_score=bad)


@pytest.mark.parametrize("alpha", [0.0, 1.0, -0.1])
def test_alpha_range(alpha):
    with pytest.raises(ValueError):
        GateConfig(alpha=alpha)


def test_config_defaults_match_protocol():
    cfg = GateConfig()
    assert cfg.alpha == 0.05
    assert cfg.min_effect == 0.05
    assert cfg.method is MethodId.RESIDUAL_CORRECTION


# --- gate input boundary -------------------------------------------------

def unlabeled_eval(family="f2", case_id="exec_simple_98"):
    return case(base=None, cand=None, split=Split.EVALUATION,
                family=family, case_id=case_id)


def test_gate_input_accepts_c_labels_and_u_predictions():
    GateInput(SPEC, SPEC, calibration=[case()], evaluation=[unlabeled_eval()])


def test_evaluation_labels_cannot_reach_gate():
    leaked = case(split=Split.EVALUATION, family="f2")
    with pytest.raises(ValueError, match="evaluation labels"):
        GateInput(SPEC, SPEC, calibration=[case()], evaluation=[leaked])


def test_wrong_split_rejected():
    with pytest.raises(ValueError):
        GateInput(SPEC, SPEC, calibration=[case(split=Split.DEVELOPMENT)], evaluation=[])


def test_family_overlap_between_splits_rejected():
    with pytest.raises(ValueError, match="families"):
        GateInput(SPEC, SPEC, calibration=[case(family="f1")],
                  evaluation=[unlabeled_eval(family="f1")])


# --- gate output ---------------------------------------------------------

def out(verdict, reason, interval=(0.06, 0.2)):
    return GateOutput(verdict=verdict, reason=reason, method=MethodId.RESIDUAL_CORRECTION,
                      protocol_version="bfcl-pilot-v0.1", estimate=0.1,
                      interval=interval, coverage_scope="finite pool, random partition")


def test_unresolved_requires_reason():
    with pytest.raises(ValueError):
        out(Verdict.UNRESOLVED, None)
    out(Verdict.UNRESOLVED, UnresolvedReason.INTERVAL_CROSSES_THRESHOLD)


def test_ship_must_not_carry_reason():
    with pytest.raises(ValueError):
        out(Verdict.SHIP, UnresolvedReason.INSUFFICIENT_SAMPLES)


def test_empty_interval_rejected():
    with pytest.raises(ValueError):
        out(Verdict.SHIP, None, interval=(0.2, 0.1))
