"""Local execution verifier for the BFCL pilot (PROTOCOL.md sections 1-2, M1 Q3).

Replaces upstream's `exec(function_call)` with:
  1. a strict parser: exactly one call to a function in the case's schema, with
     literal arguments only (ast.literal_eval), so no model-written code runs;
  2. execution in a fresh spawned worker process per call, with its own copy of
     the arguments, its own temporary working directory, socket creation
     disabled, and a timeout;
  3. upstream's exact-match comparison: top-level tuple -> list, then `==`.

The reference call runs in its own worker, never in the same process as an arm.
Agent-caused problems (bad call, exception, timeout) are failures. Reference or
worker problems are invalid measurements with a reason.
"""
from __future__ import annotations

import ast
import multiprocessing as mp
import os
import tempfile
from dataclasses import dataclass
from typing import Any

from agent_eval_gate.bfcl import Reference

VERIFIER_VERSION = "local-exact-v1"
TIMEOUT_S = 5.0
MEMORY_LIMIT_BYTES = 512 * 1024 * 1024


class CallRejected(ValueError):
    def __init__(self, reason: str, detail: str = ""):
        super().__init__(f"{reason}: {detail}" if detail else reason)
        self.reason = reason


@dataclass(frozen=True)
class ParsedCall:
    name: str
    args: tuple
    kwargs: dict


@dataclass(frozen=True)
class ExecResult:
    status: str                  # "ok" | "error" | "timeout" | "crash"
    value: Any = None
    error: str = ""
    memory_limit_enforced: bool = False


@dataclass(frozen=True)
class Verification:
    status: str                  # "pass" | "fail" | "invalid"
    reason: str = ""             # why it failed or is invalid
    output: Any = None
    verifier_version: str = VERIFIER_VERSION

    @property
    def label(self) -> int | None:
        return {"pass": 1, "fail": 0}.get(self.status)

    @property
    def invalid_reason(self) -> str | None:
        return self.reason if self.status == "invalid" else None


def parse_call(text: str, allowed: set[str]) -> ParsedCall:
    """Exactly one call `name(literal, key=literal, ...)`, optionally wrapped as `[call]`."""
    try:
        node = ast.parse(text.strip(), mode="eval").body
    except SyntaxError as e:
        raise CallRejected("unparseable", str(e)) from None
    if isinstance(node, (ast.List, ast.Tuple)):
        if len(node.elts) != 1:
            raise CallRejected("wrong_call_count", f"{len(node.elts)} calls")
        node = node.elts[0]
    if not isinstance(node, ast.Call):
        raise CallRejected("not_a_call")
    if not isinstance(node.func, ast.Name) or node.func.id not in allowed:
        raise CallRejected("unknown_function", ast.unparse(node.func))
    args, kwargs = [], {}
    try:
        for a in node.args:
            if isinstance(a, ast.Starred):
                raise ValueError("starred argument")
            args.append(ast.literal_eval(a))
        for k in node.keywords:
            if k.arg is None:
                raise ValueError("**kwargs")
            kwargs[k.arg] = ast.literal_eval(k.value)
    except (ValueError, TypeError, SyntaxError, MemoryError, RecursionError) as e:
        raise CallRejected("non_literal_argument", str(e)) from None
    return ParsedCall(node.func.id, tuple(args), kwargs)


def _disable_network() -> None:
    import socket

    def blocked(*_a, **_k):
        raise OSError("network disabled in verifier worker")

    socket.socket = blocked            # type: ignore[assignment,misc]
    socket.create_connection = blocked  # type: ignore[assignment]


def _limit_memory() -> bool:
    try:
        import resource
        resource.setrlimit(resource.RLIMIT_AS, (MEMORY_LIMIT_BYTES, MEMORY_LIMIT_BYTES))
        return True
    except (ImportError, ValueError, OSError):
        return False  # e.g. macOS does not enforce RLIMIT_AS


def _worker(name: str, args: tuple, kwargs: dict, conn) -> None:
    enforced = _limit_memory()
    _disable_network()
    with tempfile.TemporaryDirectory() as tmp:
        os.chdir(tmp)
        from agent_eval_gate.bfcl_functions import FUNCTIONS
        try:
            value = FUNCTIONS[name](*args, **kwargs)
            conn.send(("ok", value, "", enforced))
        except BaseException as e:  # noqa: BLE001 -- report every agent-caused error
            conn.send(("error", None, f"{type(e).__name__}: {e}", enforced))


def execute(call: ParsedCall, timeout: float = TIMEOUT_S) -> ExecResult:
    """Run one parsed call in a fresh spawned process. Arguments are copied by pickling."""
    ctx = mp.get_context("spawn")
    recv, send = ctx.Pipe(duplex=False)
    proc = ctx.Process(target=_worker, args=(call.name, call.args, call.kwargs, send))
    proc.start()
    send.close()
    try:
        if not recv.poll(timeout):
            return ExecResult("timeout", error=f"exceeded {timeout}s")
        try:
            status, value, error, enforced = recv.recv()
        except (EOFError, OSError) as e:
            return ExecResult("crash", error=f"no result from worker: {e!r}")
        return ExecResult(status, value, error, enforced)
    finally:
        if proc.is_alive():
            proc.kill()
        proc.join()
        recv.close()


def _normalize(value: Any) -> Any:
    """Upstream converts a top-level tuple result to a list before comparing."""
    return list(value) if isinstance(value, tuple) else value


def run_reference(ref: Reference, timeout: float = TIMEOUT_S) -> ExecResult:
    """Execute the reference call in its own worker. Not shown to agents or judges."""
    from agent_eval_gate.bfcl_functions import FUNCTIONS
    if len(ref.ground_truth) != 1:
        return ExecResult("crash", error="reference must be exactly one call")
    try:
        call = parse_call(ref.ground_truth[0], set(FUNCTIONS))
    except CallRejected as e:
        return ExecResult("crash", error=f"reference rejected: {e}")
    return execute(call, timeout)


def verify(call_text: str, allowed: set[str], reference: ExecResult,
           timeout: float = TIMEOUT_S) -> Verification:
    """Verify one arm's call against an already-executed reference result."""
    if reference.status != "ok":
        return Verification("invalid", f"reference_{reference.status}")
    try:
        call = parse_call(call_text, allowed)
    except CallRejected as e:
        return Verification("fail", e.reason)
    result = execute(call, timeout)
    if result.status == "crash":
        return Verification("invalid", "worker_crash")
    if result.status == "timeout":
        return Verification("fail", "timeout")
    if result.status == "error":
        return Verification("fail", "execution_error", result.error)
    out = _normalize(result.value)
    if out == _normalize(reference.value):
        return Verification("pass", output=out)
    return Verification("fail", "wrong_result", out)
