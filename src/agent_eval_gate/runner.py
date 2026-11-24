"""Paired agent runner for the BFCL pilot (PROTOCOL.md section 3, M1 Q4 and Q7).

Both arms get the same question and tool schema; only the system prompt
differs. Each arm is a separate, freshly built provider request, and each
arm's call is verified in its own worker. The provider is an interface so the
runner can be tested without paid calls; the real OpenAI client comes later.
"""
from __future__ import annotations

import copy
import hashlib
import json
import random
import time
from dataclasses import dataclass, field
from typing import Callable, Protocol

from agent_eval_gate.bfcl import CaseInput
from agent_eval_gate.contract import VariantSpec
from agent_eval_gate.verifier import ExecResult, Verification, verify

BASELINE_PROMPT = (
    "Select the function call that fulfills the user's request using the provided\n"
    "tool schema. Return exactly one function call with its arguments. Do not add\n"
    "prose, execute code, or invent tools or arguments."
)
CANDIDATE_SUFFIX = (
    "Before returning the call, check required arguments, units, and defaults\n"
    "against the user's request and the tool schema."
)
CANDIDATE_PROMPT = BASELINE_PROMPT + "\n" + CANDIDATE_SUFFIX

ARM_ORDER_SEED = 20261122
MAX_RETRIES = 2
RETRY_DELAYS_S = (1.0, 2.0)
REQUEST_TIMEOUT_S = 120.0


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class TransportError(Exception):
    """Rate limit, network failure, or server error: retryable, never a content judgment."""


@dataclass(frozen=True)
class ProviderResponse:
    text: str
    model: str                       # model identifier the provider reports
    usage: dict = field(default_factory=dict)
    request_id: str = ""


class Provider(Protocol):
    def complete(self, request: dict) -> ProviderResponse: ...


@dataclass(frozen=True)
class Attempt:
    started: float
    seconds: float
    error: str = ""                  # empty on success


@dataclass(frozen=True)
class ArmRecord:
    arm: str                         # "baseline" | "candidate"
    request: dict
    attempts: tuple[Attempt, ...]
    response: ProviderResponse | None
    verification: Verification


@dataclass(frozen=True)
class PairRecord:
    case_id: str
    family_id: str
    first_arm: str                   # which arm was requested first
    baseline: ArmRecord
    candidate: ArmRecord


def build_request(case: CaseInput, system_prompt: str, spec: VariantSpec) -> dict:
    """A fresh request: system prompt + tool schema, then the unmodified question turns."""
    schema = json.dumps(case.functions, indent=2, sort_keys=True)
    messages = [{"role": "system", "content": f"{system_prompt}\n\nTool schema:\n{schema}"}]
    for turn in case.question:           # BFCL nests turns as a list of lists
        messages.extend(copy.deepcopy(turn))
    return {
        "model": spec.model_snapshot,
        "messages": messages,
        "temperature": spec.temperature,
        "top_p": spec.top_p,
        "max_tokens": spec.max_output_tokens,
        "timeout": REQUEST_TIMEOUT_S,
    }


def tool_schema_hash(cases: list[CaseInput]) -> str:
    blob = json.dumps({c.case_id: c.functions for c in cases}, sort_keys=True)
    return sha256_text(blob)


def make_variant(model: str, prompt: str, cases: list[CaseInput]) -> VariantSpec:
    return VariantSpec(model_snapshot=model, prompt_hash=sha256_text(prompt),
                       tool_schema_hash=tool_schema_hash(cases),
                       temperature=0.0, top_p=1.0, max_output_tokens=2048)


def arm_order_schedule(case_ids: list[str], seed: int = ARM_ORDER_SEED) -> dict[str, str]:
    """Which arm is requested first, per case: seeded, over string-sorted IDs."""
    rng = random.Random(seed)
    return {cid: ("baseline" if rng.random() < 0.5 else "candidate")
            for cid in sorted(case_ids)}


def call_with_retries(provider: Provider, request: dict,
                      sleep: Callable[[float], None] = time.sleep,
                      clock: Callable[[], float] = time.time,
                      ) -> tuple[ProviderResponse | None, tuple[Attempt, ...]]:
    """At most 1 + MAX_RETRIES attempts; only TransportError is retried. Every attempt is kept."""
    attempts: list[Attempt] = []
    for i in range(1 + MAX_RETRIES):
        start = clock()
        try:
            response = provider.complete(copy.deepcopy(request))
            attempts.append(Attempt(start, clock() - start))
            return response, tuple(attempts)
        except TransportError as e:
            attempts.append(Attempt(start, clock() - start, f"transport: {e}"))
            if i < MAX_RETRIES:
                sleep(RETRY_DELAYS_S[i])
    return None, tuple(attempts)


def run_arm(arm: str, case: CaseInput, prompt: str, spec: VariantSpec,
            provider: Provider, reference: ExecResult,
            sleep: Callable[[float], None] = time.sleep) -> ArmRecord:
    request = build_request(case, prompt, spec)
    response, attempts = call_with_retries(provider, request, sleep=sleep)
    if response is None:
        verification = Verification("invalid", "transport_failed")
    else:
        allowed = {f["name"] for f in case.functions}
        verification = verify(response.text, allowed, reference)
    return ArmRecord(arm, request, attempts, response, verification)


def run_pair(case: CaseInput, reference: ExecResult, provider: Provider,
             baseline: VariantSpec, candidate: VariantSpec, first_arm: str,
             sleep: Callable[[float], None] = time.sleep) -> PairRecord:
    """Run both arms in the scheduled order. Both are always recorded."""
    arms = {"baseline": (BASELINE_PROMPT, baseline), "candidate": (CANDIDATE_PROMPT, candidate)}
    order = [first_arm, "candidate" if first_arm == "baseline" else "baseline"]
    records: dict[str, ArmRecord] = {}
    for arm in order:
        prompt, spec = arms[arm]
        records[arm] = run_arm(arm, case, prompt, spec, provider, reference, sleep)
    return PairRecord(case.case_id, case.family_id, first_arm,
                      records["baseline"], records["candidate"])
