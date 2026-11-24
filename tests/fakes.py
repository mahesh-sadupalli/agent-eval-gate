"""Shared test fakes: one development-style case and a fake agent provider (no paid calls)."""
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
