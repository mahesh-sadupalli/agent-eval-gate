"""Run records, resume, and call-cap tests on the 12 development cases (fakes, no paid calls)."""
import json
from collections import Counter
from pathlib import Path

import pytest

from agent_eval_gate.bfcl import BFCL_COMMIT, QUESTIONS_FILE, load_case_inputs, load_references
from agent_eval_gate.collect import CallBudget, collect
from agent_eval_gate.contract import Split
from agent_eval_gate.runner import (
    BASELINE_PROMPT,
    CANDIDATE_PROMPT,
    CANDIDATE_SUFFIX,
    ProviderResponse,
    TransportError,
    make_variant,
)
from agent_eval_gate.store import ARMS_FILE, CONFIG_FILE, JUDGE_FILE, RunStore, default_config

DATA = Path(__file__).resolve().parents[1] / "data" / "bfcl" / BFCL_COMMIT
pytestmark = pytest.mark.skipif(not (DATA / QUESTIONS_FILE).is_file(),
                                reason="run scripts/fetch_bfcl.py first")

no_sleep = lambda _s: None  # noqa: E731


@pytest.fixture(scope="module")
def dev():
    cases = [c for c in load_case_inputs(DATA) if c.split is Split.DEVELOPMENT]
    return cases, load_references(DATA)


class Agent:
    """Baseline returns the reference call; candidate returns a call with no arguments."""

    def __init__(self, cases, refs, fail_on=(), crash_after=None):
        self.by_question = {json.dumps(c.question[0]): (refs[c.case_id].ground_truth[0],
                                                        c.functions[0]["name"]) for c in cases}
        self.fail_on, self.crash_after, self.calls = set(fail_on), crash_after, 0

    def complete(self, request):
        self.calls += 1
        if self.crash_after is not None and self.calls > self.crash_after:
            raise KeyboardInterrupt("simulated interruption")
        good, name = self.by_question[json.dumps(request["messages"][1:])]
        arm = "candidate" if CANDIDATE_SUFFIX in request["messages"][0]["content"] else "baseline"
        if (name, arm) in self.fail_on:
            raise TransportError("503")
        return ProviderResponse(good if arm == "baseline" else f"{name}()", request["model"])


class Judge:
    def complete(self, request):
        return ProviderResponse('{"p_A": 0.8, "p_B": 0.3}', request["model"])


def setup(tmp_path, dev, model="fake-agent-2026-01-01"):
    cases, refs = dev
    store = RunStore(tmp_path, default_config(model))
    b = make_variant(model, BASELINE_PROMPT, cases)
    c = make_variant(model, CANDIDATE_PROMPT, cases)
    return cases, refs, store, b, c


def lines(store, name):
    return (store.dir / name).read_text().splitlines()


def test_full_development_run(tmp_path, dev):
    cases, refs, store, b, c = setup(tmp_path, dev)
    s = collect(cases, refs, Agent(cases, refs), Judge(), store, b, c, CallBudget(1000), sleep=no_sleep)
    assert s.complete and (s.arm_calls, s.judge_calls) == (24, 12)
    arms = store.arms()
    assert all(arms[(x.case_id, "baseline")].verification.label == 1 for x in cases)
    assert all(arms[(x.case_id, "candidate")].verification.label == 0 for x in cases)
    assert len(store.judgments()) == 12


def test_rerun_of_complete_run_makes_no_calls(tmp_path, dev):
    cases, refs, store, b, c = setup(tmp_path, dev)
    collect(cases, refs, Agent(cases, refs), Judge(), store, b, c, CallBudget(1000), sleep=no_sleep)
    agent = Agent(cases, refs)
    s = collect(cases, refs, agent, Judge(), RunStore(tmp_path, store.config), b, c,
                CallBudget(1000), sleep=no_sleep)
    assert s.complete and agent.calls == 0 and (s.arm_calls, s.judge_calls) == (0, 0)


def test_budget_stop_then_resume_without_duplicates(tmp_path, dev):
    cases, refs, store, b, c = setup(tmp_path, dev)
    s1 = collect(cases, refs, Agent(cases, refs), Judge(), store, b, c, CallBudget(20), sleep=no_sleep)
    assert not s1.complete and s1.stopped_reason.startswith("budget")
    before = lines(store, ARMS_FILE)
    s2 = collect(cases, refs, Agent(cases, refs), Judge(), store, b, c, CallBudget(1000), sleep=no_sleep)
    after = lines(store, ARMS_FILE)
    assert s2.complete
    assert after[:len(before)] == before                      # earlier records untouched
    keys = Counter((json.loads(x)["case_id"], json.loads(x)["record"]["arm"]) for x in after)
    assert len(keys) == 24 and set(keys.values()) == {1}
    assert len(lines(store, JUDGE_FILE)) == 12


def test_interruption_then_resume(tmp_path, dev):
    cases, refs, store, b, c = setup(tmp_path, dev)
    with pytest.raises(KeyboardInterrupt):
        collect(cases, refs, Agent(cases, refs, crash_after=7), Judge(), store, b, c,
                CallBudget(1000), sleep=no_sleep)
    assert len(lines(store, ARMS_FILE)) == 7
    s = collect(cases, refs, Agent(cases, refs), Judge(), store, b, c, CallBudget(1000), sleep=no_sleep)
    assert s.complete and s.arm_calls == 17
    assert len(lines(store, ARMS_FILE)) == 24


def test_transport_failure_is_kept_and_retried_on_resume(tmp_path, dev):
    cases, refs, store, b, c = setup(tmp_path, dev)
    s1 = collect(cases, refs, Agent(cases, refs, fail_on={("book_room", "candidate")}), Judge(),
                 store, b, c, CallBudget(1000), sleep=no_sleep)
    assert not s1.complete and len(s1.pending) == 2           # book_room has 2 cases
    s2 = collect(cases, refs, Agent(cases, refs), Judge(), store, b, c, CallBudget(1000), sleep=no_sleep)
    assert s2.complete and s2.arm_calls == 2
    rows = [json.loads(x) for x in lines(store, ARMS_FILE)]
    failed = [r for r in rows if r["record"]["verification"]["reason"] == "transport_failed"]
    assert len(failed) == 2 and all(len(r["record"]["attempts"]) == 3 for r in failed)


def test_accepted_record_cannot_be_overwritten(tmp_path, dev):
    cases, refs, store, b, c = setup(tmp_path, dev)
    collect(cases, refs, Agent(cases, refs), Judge(), store, b, c, CallBudget(1000), sleep=no_sleep)
    cid = cases[0].case_id
    with pytest.raises(RuntimeError, match="accepted"):
        store.write_arm(cid, store.arms()[(cid, "baseline")])
    with pytest.raises(RuntimeError, match="accepted"):
        store.write_judgment(store.judgments()[cid])


def test_changed_config_is_a_new_run(tmp_path, dev):
    s1 = RunStore(tmp_path, default_config("model-a"))
    s2 = RunStore(tmp_path, default_config("model-b"))
    assert s1.run_id != s2.run_id and s1.dir != s2.dir


def test_tampered_config_file_refuses_to_resume(tmp_path):
    s = RunStore(tmp_path, default_config("model-a"))
    (s.dir / CONFIG_FILE).write_text(json.dumps({"agent_model": "other"}))
    with pytest.raises(RuntimeError, match="differs"):
        RunStore(tmp_path, default_config("model-a"))


def test_evaluation_cases_are_refused(tmp_path, dev):
    _, refs, store, b, c = setup(tmp_path, dev)
    ev = [x for x in load_case_inputs(DATA) if x.split is Split.EVALUATION][:2]
    with pytest.raises(ValueError, match="reserved"):
        collect(ev, refs, Agent(ev, refs), Judge(), store, b, c, CallBudget(1000))
