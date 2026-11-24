"""Shared test fakes: a development-style case, fake agent and judge providers (no paid calls)."""
import json

from agent_eval_gate.bfcl import CaseInput
from agent_eval_gate.contract import Split
from agent_eval_gate.runner import (
    BASELINE_PROMPT,
    CANDIDATE_PROMPT,
    CANDIDATE_SUFFIX,
    ProviderResponse,
    TransportError,
    make_variant,
)
from agent_eval_gate.verifier import ExecResult

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
