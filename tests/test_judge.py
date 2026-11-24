"""Blinded-judge tests with a fake provider: no paid calls (M1 Q5)."""
import json
from collections import Counter

import pytest

from agent_eval_gate.bfcl import case_index
from agent_eval_gate.contract import Position, Split
from agent_eval_gate.judge import (
    JUDGE_PROMPT,
    JudgeParseError,
    judge_pair,
    parse_scores,
    position_schedule,
    to_case_result,
)
from agent_eval_gate.runner import ProviderResponse, TransportError, run_pair
from fakes import CAND, CASE, REFERENCE, SPEC, FakeProvider, no_sleep

GOOD = "calculate_triangle_area(base=10, height=5)"
BAD = "calculate_triangle_area(base=10, height=6)"


class FakeJudge:
    """Gives 0.9 to whichever shown response contains GOOD, 0.2 otherwise."""

    def __init__(self, raw=None, fail=0):
        self.raw, self.fail, self.requests = raw, fail, []

    def complete(self, request):
        self.requests.append(request)
        if self.fail:
            self.fail -= 1
            raise TransportError("503")
        if self.raw is not None:
            return ProviderResponse(self.raw, request["model"])
        shown = json.loads(request["messages"][1]["content"])
        score = lambda t: 0.9 if t == GOOD else 0.2  # noqa: E731
        return ProviderResponse(json.dumps({"p_A": score(shown["response_A"]),
                                            "p_B": score(shown["response_B"])}), request["model"])


def pair(baseline=BAD, candidate=GOOD):
    return run_pair(CASE, REFERENCE, FakeProvider(baseline, candidate), SPEC, CAND,
                    "baseline", sleep=no_sleep)


# --- schedule ------------------------------------------------------------------------

def test_schedule_is_balanced_within_every_manifest_family():
    families = {cid: fam for cid, (fam, _) in case_index().items()}
    sched = position_schedule(families)
    assert len(sched) == 60
    for fam in set(families.values()):
        counts = Counter(sched[c] for c, f in families.items() if f == fam)
        assert counts[Position.AB] == counts[Position.BA]


def test_schedule_is_reproducible_and_seed_dependent():
    families = {cid: fam for cid, (fam, _) in case_index().items()}
    assert position_schedule(families) == position_schedule(dict(reversed(families.items())))
    assert position_schedule(families, seed=1) != position_schedule(families)


def test_odd_family_rejected():
    with pytest.raises(ValueError):
        position_schedule({"a": "f", "b": "f", "c": "f"})


# --- blinding --------------------------------------------------------------------------

@pytest.mark.parametrize("position", [Position.AB, Position.BA])
def test_judge_request_is_blinded(position):
    j = FakeJudge()
    judge_pair(CASE, pair(), position, j, sleep=no_sleep)
    req = j.requests[0]
    assert req["messages"][0]["content"] == JUDGE_PROMPT        # fixed rubric text
    blob = req["messages"][1]["content"] + req["model"]          # everything case-specific
    for leaked in ["baseline", "candidate", SPEC.model_snapshot, "wrong_result",
                   "25.0", "verif", "Before returning the call"]:
        assert leaked not in blob, leaked


# --- AB/BA mapping -------------------------------------------------------------------------

@pytest.mark.parametrize("position", [Position.AB, Position.BA])
def test_sign_survives_order_reversal(position):
    """Candidate is the good call in both orders, so candidate - baseline stays +0.7."""
    rec = judge_pair(CASE, pair(baseline=BAD, candidate=GOOD), position, FakeJudge(), sleep=no_sleep)
    assert (rec.p_baseline, rec.p_candidate) == (0.2, 0.9)


def test_ab_shows_baseline_first_and_ba_candidate_first():
    for position, first in [(Position.AB, BAD), (Position.BA, GOOD)]:
        j = FakeJudge()
        judge_pair(CASE, pair(baseline=BAD, candidate=GOOD), position, j, sleep=no_sleep)
        assert json.loads(j.requests[0]["messages"][1]["content"])["response_A"] == first


# --- parsing and missing judgments ------------------------------------------------------------

@pytest.mark.parametrize("raw", [
    "", "0.5, 0.5", '{"p_A": 0.5}', '{"p_A": 0.5, "p_B": 0.5, "why": "x"}',
    '{"p_A": 1.2, "p_B": 0.5}', '{"p_A": -0.1, "p_B": 0.5}', '{"p_A": NaN, "p_B": 0.5}',
    '{"p_A": "0.5", "p_B": 0.5}', '{"p_A": true, "p_B": 0.5}', '```json\n{"p_A": 0.5, "p_B": 0.5}\n```',
])
def test_bad_judge_output_rejected(raw):
    with pytest.raises(JudgeParseError):
        parse_scores(raw)


def test_valid_scores_parse():
    assert parse_scores(' {"p_B": 0, "p_A": 1} ') == (1.0, 0.0)


def test_bad_output_becomes_missing_not_zero():
    rec = judge_pair(CASE, pair(), Position.AB, FakeJudge(raw="I think A."), sleep=no_sleep)
    assert rec.p_baseline is None and rec.p_candidate is None
    assert rec.error.startswith("parse_error")


def test_transport_failure_is_missing():
    rec = judge_pair(CASE, pair(), Position.AB, FakeJudge(fail=3), sleep=no_sleep)
    assert rec.error == "transport_failed" and len(rec.attempts) == 3


def test_missing_arm_is_not_judged():
    p = run_pair(CASE, REFERENCE, FakeProvider(fail_first=3), SPEC, CAND, "baseline", sleep=no_sleep)
    j = FakeJudge()
    rec = judge_pair(CASE, p, Position.AB, j, sleep=no_sleep)
    assert rec.error == "arm_missing" and j.requests == []


# --- contract bridge -------------------------------------------------------------------------------

def test_to_case_result_restores_identity():
    p = pair(baseline=BAD, candidate=GOOD)
    rec = judge_pair(CASE, p, Position.BA, FakeJudge(), sleep=no_sleep)
    cr = to_case_result(p, rec, Split.DEVELOPMENT, "run-0")
    assert (cr.baseline_verified, cr.candidate_verified) == (0, 1)
    assert cr.judge_delta == pytest.approx(0.7)
    assert cr.verified_delta == 1 and cr.position is Position.BA
