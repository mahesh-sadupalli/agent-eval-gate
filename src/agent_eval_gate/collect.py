"""Collect one paired run with resume and a call cap (M1 Q7, Q8).

For each case in the seeded arm order: run any arm without an accepted record,
then judge the pair if it has no accepted judgment. Accepted work is reused,
never repeated. Evaluation cases are refused unless explicitly allowed (M3).
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable

from agent_eval_gate.bfcl import CaseInput, Reference
from agent_eval_gate.contract import Split, VariantSpec
from agent_eval_gate.judge import JUDGE_MODEL, judge_pair, position_schedule
from agent_eval_gate.runner import (
    BASELINE_PROMPT,
    CANDIDATE_PROMPT,
    MAX_RETRIES,
    PairRecord,
    Provider,
    arm_order_schedule,
    run_arm,
)
from agent_eval_gate.store import RunStore, arm_accepted, judge_accepted
from agent_eval_gate.verifier import run_reference


class BudgetExhausted(Exception):
    pass


@dataclass
class CallBudget:
    """Caps provider attempts (retries included). Reserves the worst case per request."""
    max_attempts: int
    used: int = 0

    def reserve(self) -> None:
        if self.used + 1 + MAX_RETRIES > self.max_attempts:
            raise BudgetExhausted(f"{self.used}/{self.max_attempts} attempts used")

    def spend(self, n: int) -> None:
        self.used += n


@dataclass
class Summary:
    run_id: str
    complete: bool
    stopped_reason: str = ""
    arm_calls: int = 0
    judge_calls: int = 0
    pending: list[str] = field(default_factory=list)


def collect(cases: list[CaseInput], references: dict[str, Reference], agent: Provider,
            judge: Provider, store: RunStore, baseline: VariantSpec, candidate: VariantSpec,
            budget: CallBudget, judge_model: str = JUDGE_MODEL, allow_evaluation: bool = False,
            sleep: Callable[[float], None] = time.sleep) -> Summary:
    if not allow_evaluation and any(c.split is Split.EVALUATION for c in cases):
        raise ValueError("evaluation cases are reserved for M3")
    by_id = {c.case_id: c for c in cases}
    order = arm_order_schedule(list(by_id))
    positions = position_schedule({c.case_id: c.family_id for c in cases})
    prompts = {"baseline": (BASELINE_PROMPT, baseline), "candidate": (CANDIDATE_PROMPT, candidate)}
    summary = Summary(store.run_id, complete=False)

    try:
        for cid, first in order.items():
            case = by_id[cid]
            arms = store.arms()
            missing = [a for a in (first, "candidate" if first == "baseline" else "baseline")
                       if (cid, a) not in arms or not arm_accepted(arms[(cid, a)])]
            if missing:
                reference = run_reference(references[cid])
                for arm in missing:
                    budget.reserve()
                    prompt, spec = prompts[arm]
                    rec = run_arm(arm, case, prompt, spec, agent, reference, sleep)
                    budget.spend(len(rec.attempts))
                    summary.arm_calls += 1
                    store.write_arm(cid, rec)
                arms = store.arms()
            prev = store.judgments().get(cid)
            if prev is None or not judge_accepted(prev):
                pair = PairRecord(cid, case.family_id, first,
                                  arms[(cid, "baseline")], arms[(cid, "candidate")])
                if pair.baseline.response is None or pair.candidate.response is None:
                    summary.pending.append(cid)
                    continue
                budget.reserve()
                rec = judge_pair(case, pair, positions[cid], judge, judge_model, sleep)
                budget.spend(len(rec.attempts))
                summary.judge_calls += 1
                store.write_judgment(rec)
                if not judge_accepted(rec):
                    summary.pending.append(cid)
    except BudgetExhausted as e:
        summary.stopped_reason = f"budget: {e}"
        return summary

    summary.complete = not summary.pending
    if summary.pending:
        summary.stopped_reason = "transport failures remain; resume to retry"
    return summary
