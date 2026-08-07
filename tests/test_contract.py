"""Tests for the frozen contract.

The load-bearing behaviour here is `is_truth_tied`: it selects the subpopulation
the differential-bias estimator is built on. If it silently
under-selects, the estimator collapses and the gate returns need_more_n with no
error raised — so the tolerance behaviour gets an explicit regression test.
"""
import pytest

from agent_eval_gate.contract import GROUND_TRUTH_TOL, CaseResult, Position


def case(base_gt, cand_gt, base_score=0.5, cand_score=0.5):
    return CaseResult(
        case_id="c",
        domain="bfcl",
        baseline_score=base_score,
        candidate_score=cand_score,
        judge_version="judge-v1",
        position=Position.AB,
        baseline_ground_truth=base_gt,
        candidate_ground_truth=cand_gt,
    )


def test_judge_delta_is_candidate_minus_baseline():
    assert case(1.0, 1.0, base_score=0.4, cand_score=0.7).judge_delta == pytest.approx(0.3)


@pytest.mark.parametrize("gt", [0.0, 1.0])
def test_both_arms_same_outcome_is_tied(gt):
    """Both-pass and both-fail are both tied; sec. 6.2 stratifies them separately."""
    assert case(gt, gt).is_truth_tied


def test_differing_outcomes_are_not_tied():
    assert not case(0.0, 1.0).is_truth_tied
    assert not case(1.0, 0.0).is_truth_tied


@pytest.mark.parametrize("base,cand", [(None, 1.0), (1.0, None), (None, None)])
def test_missing_ground_truth_is_never_tied(base, cand):
    """No verifiable outcome means the true delta is unknown, not zero."""
    assert not case(base, cand).is_truth_tied


def test_float_representation_noise_still_counts_as_tied():
    """Regression: exact `==` would drop this case and shrink the tied set."""
    assert case(0.1 + 0.2, 0.3).is_truth_tied


def test_distinct_graded_levels_are_not_tied():
    """The tolerance must not swallow genuinely different outcome bands."""
    assert not case(0.5, 0.5 + 10 * GROUND_TRUTH_TOL).is_truth_tied
