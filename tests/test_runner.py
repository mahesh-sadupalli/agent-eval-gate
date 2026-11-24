"""Paired-runner tests with a fake provider: no paid calls (M1 Q4, Q7)."""
import json
from pathlib import Path

import pytest

from agent_eval_gate.bfcl import BFCL_COMMIT, QUESTIONS_FILE, CaseInput, load_case_inputs, load_references
from agent_eval_gate.contract import Split
from agent_eval_gate.runner import (
    BASELINE_PROMPT,
    CANDIDATE_PROMPT,
    CANDIDATE_SUFFIX,
    MAX_RETRIES,
    ProviderResponse,
    TransportError,
    arm_order_schedule,
    build_request,
    call_with_retries,
    make_variant,
    run_pair,
)
from agent_eval_gate.verifier import ExecResult, run_reference

DATA = Path(__file__).resolve().parents[1] / "data" / "bfcl" / BFCL_COMMIT
needs_data = pytest.mark.skipif(not (DATA / QUESTIONS_FILE).is_file(),
                                reason="run scripts/fetch_bfcl.py first")

CASE = CaseInput(
    case_id="exec_simple_20", family_id="calculate_triangle_area", split=Split.DEVELOPMENT,
    question=[[{"role": "user", "content": "Area of a triangle with base 10 and height 5?"}]],
    functions=[{"name": "calculate_triangle_area", "description": "Area.",
                "parameters": {"type": "dict", "properties": {}, "required": []}}],
)
SPEC = make_variant("fake-model-2026-01-01", BASELINE_PROMPT, [CASE])
CAND = make_variant("fake-model-2026-01-01", CANDIDATE_PROMPT, [CASE])
REFERENCE = ExecResult("ok", 25.0)
no_sleep = lambda _s: None  # noqa: E731


class FakeProvider:
    """Answers by arm (detected from the system prompt); can inject transport failures."""

    def __init__(self, baseline="calculate_triangle_area(base=10, height=5)",
                 candidate="calculate_triangle_area(base=10, height=5)", fail_first=0):
        self.answers = {"baseline": baseline, "candidate": candidate}
        self.fail_first = fail_first
        self.requests = []

    def complete(self, request):
        self.requests.append(request)
        if self.fail_first > 0:
            self.fail_first -= 1
            raise TransportError("429 rate limited")
        arm = "candidate" if CANDIDATE_SUFFIX in request["messages"][0]["content"] else "baseline"
        return ProviderResponse(self.answers[arm], request["model"], {"total_tokens": 10})


# --- requests ------------------------------------------------------------------

def test_arms_differ_only_in_system_prompt():
    b, c = build_request(CASE, BASELINE_PROMPT, SPEC), build_request(CASE, CANDIDATE_PROMPT, CAND)
    assert b["messages"][1:] == c["messages"][1:]
    assert c["messages"][0]["content"].replace("\n" + CANDIDATE_SUFFIX, "") == b["messages"][0]["content"]
    assert {k: v for k, v in b.items() if k != "messages"} == \
           {k: v for k, v in c.items() if k != "messages"}


def test_request_carries_question_and_schema_unmodified():
    r = build_request(CASE, BASELINE_PROMPT, SPEC)
    assert r["messages"][1] == CASE.question[0][0]
    assert json.dumps(CASE.functions, indent=2, sort_keys=True) in r["messages"][0]["content"]


def test_requests_are_independent_copies():
    r = build_request(CASE, BASELINE_PROMPT, SPEC)
    r["messages"][1]["content"] = "tampered"
    assert CASE.question[0][0]["content"] != "tampered"


@needs_data
def test_requests_contain_no_reference_answer():
    refs = load_references(DATA)
    for c in load_case_inputs(DATA):
        blob = json.dumps(build_request(c, CANDIDATE_PROMPT, CAND))
        assert refs[c.case_id].ground_truth[0] not in blob


# --- order schedule ----------------------------------------------------------------

def test_arm_order_is_seeded_and_reproducible():
    ids = [f"exec_simple_{i}" for i in range(60)]
    a, b = arm_order_schedule(ids), arm_order_schedule(list(reversed(ids)))
    assert a == b
    assert set(a.values()) == {"baseline", "candidate"}
    assert arm_order_schedule(ids, seed=1) != a


@pytest.mark.parametrize("first", ["baseline", "candidate"])
def test_pair_follows_schedule_and_maps_arms(first):
    p = FakeProvider(baseline="calculate_triangle_area(base=10, height=5)",
                     candidate="calculate_triangle_area(base=10, height=6)")
    rec = run_pair(CASE, REFERENCE, p, SPEC, CAND, first, sleep=no_sleep)
    first_prompt = p.requests[0]["messages"][0]["content"]
    assert (CANDIDATE_SUFFIX in first_prompt) == (first == "candidate")
    assert rec.baseline.verification.label == 1
    assert (rec.candidate.verification.label, rec.candidate.verification.reason) == (0, "wrong_result")


# --- retries and errors ----------------------------------------------------------------

def test_transport_error_is_retried_and_every_attempt_kept():
    delays = []
    resp, attempts = call_with_retries(FakeProvider(fail_first=2), {"model": "m", "messages": [
        {"role": "system", "content": BASELINE_PROMPT}]}, sleep=delays.append)
    assert resp is not None
    assert len(attempts) == 3 and [bool(a.error) for a in attempts] == [True, True, False]
    assert delays == [1.0, 2.0]


def test_exhausted_retries_make_arm_invalid_not_failed():
    p = FakeProvider(fail_first=1 + MAX_RETRIES)
    rec = run_pair(CASE, REFERENCE, p, SPEC, CAND, "baseline", sleep=no_sleep)
    assert rec.baseline.verification.label is None
    assert rec.baseline.verification.invalid_reason == "transport_failed"
    assert rec.candidate.verification.label == 1       # the other arm is still recorded


def test_malformed_answer_is_failure_and_not_retried():
    p = FakeProvider(baseline="Sure! Here is the call you asked for.")
    rec = run_pair(CASE, REFERENCE, p, SPEC, CAND, "baseline", sleep=no_sleep)
    assert rec.baseline.verification.label == 0
    assert len(rec.baseline.attempts) == 1


def test_identical_configurations_smoke():
    """Wiring check: same spec and prompt on both sides still yields two separate records."""
    p = FakeProvider()
    rec = run_pair(CASE, REFERENCE, p, SPEC, SPEC, "baseline", sleep=no_sleep)
    assert len(p.requests) == 2
    assert rec.baseline.request is not rec.candidate.request


@needs_data
def test_development_case_end_to_end_with_fake_provider():
    refs = load_references(DATA)
    case = next(c for c in load_case_inputs(DATA) if c.case_id == "exec_simple_20")
    reference = run_reference(refs[case.case_id])
    p = FakeProvider(baseline=refs[case.case_id].ground_truth[0], candidate="calculate_triangle_area()")
    rec = run_pair(case, reference, p, SPEC, CAND, "candidate", sleep=no_sleep)
    assert rec.baseline.verification.label == 1
    assert rec.candidate.verification.reason == "execution_error"   # missing arguments
