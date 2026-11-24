"""Verifier tests on development fixtures only (PROTOCOL.md section 7, M1 Q3).

Calibration and evaluation references are not executed here.
"""
import ast
from pathlib import Path

import pytest

from agent_eval_gate import bfcl_functions
from agent_eval_gate.bfcl import BFCL_COMMIT, QUESTIONS_FILE, Reference, load_case_inputs, load_references
from agent_eval_gate.bfcl_functions import FUNCTIONS
from agent_eval_gate.contract import Split
from agent_eval_gate.verifier import (
    CallRejected,
    ExecResult,
    ParsedCall,
    _normalize,
    execute,
    parse_call,
    run_reference,
    verify,
)

DATA = Path(__file__).resolve().parents[1] / "data" / "bfcl" / BFCL_COMMIT
UPSTREAM = DATA / "upstream_src" / "executable_python_function.py"
needs_data = pytest.mark.skipif(not (DATA / QUESTIONS_FILE).is_file(),
                                reason="run scripts/fetch_bfcl.py first")

TRI = {"calculate_triangle_area"}


def ref(call: str) -> Reference:
    return Reference("fixture", [call], ["exact_match"])


# --- parser ----------------------------------------------------------------

def test_parses_keyword_and_positional_literals():
    c = parse_call("calculate_triangle_area(10, height=5)", TRI)
    assert c == ParsedCall("calculate_triangle_area", (10,), {"height": 5})


def test_single_call_in_list_is_accepted():
    assert parse_call("[calculate_triangle_area(base=1, height=2)]", TRI).name == "calculate_triangle_area"


@pytest.mark.parametrize("text,reason", [
    ("calculate_triangle_area(base=1, height=2", "unparseable"),
    ("[calculate_triangle_area(base=1, height=2), calculate_triangle_area(base=2, height=2)]",
     "wrong_call_count"),
    ("42", "not_a_call"),
    ("math_factorial(n=3)", "unknown_function"),          # real function, not in schema
    ("os.system('ls')", "unknown_function"),
    ("__import__('os').system('ls')", "unknown_function"),
    ("calculate_triangle_area(base=1+1, height=2)", "non_literal_argument"),
    ("calculate_triangle_area(base=__import__('os'), height=2)", "non_literal_argument"),
    ("calculate_triangle_area(*[1, 2])", "non_literal_argument"),
    ("calculate_triangle_area(**{'base': 1, 'height': 2})", "non_literal_argument"),
])
def test_rejected_calls(text, reason):
    with pytest.raises(CallRejected) as e:
        parse_call(text, TRI)
    assert e.value.reason == reason


# --- outcomes ----------------------------------------------------------------

def test_correct_call_passes_and_changed_result_fails():
    reference = run_reference(ref("calculate_triangle_area(base=10, height=5)"))
    assert reference.status == "ok" and reference.value == 25.0
    assert verify("calculate_triangle_area(height=5, base=10)", TRI, reference).label == 1
    wrong = verify("calculate_triangle_area(base=10, height=6)", TRI, reference)
    assert (wrong.label, wrong.reason) == (0, "wrong_result")


def test_invalid_call_is_failure_not_invalid():
    reference = run_reference(ref("calculate_triangle_area(base=10, height=5)"))
    v = verify("print('hi')", TRI, reference)
    assert (v.label, v.reason) == (0, "unknown_function")


def test_agent_exception_is_failure():
    reference = run_reference(ref("calculate_density(mass=10, volume=2)"))
    v = verify("calculate_density(mass=10, volume=0)", {"calculate_density"}, reference)
    assert (v.label, v.reason) == (0, "execution_error")


def test_agent_timeout_is_failure():
    reference = ExecResult("ok", 1)
    v = verify("math_factorial(n=10000000)", {"math_factorial"}, reference, timeout=0.5)
    assert (v.label, v.reason) == (0, "timeout")


def test_broken_reference_is_invalid_measurement():
    reference = run_reference(ref("not_a_function(x=1)"))
    v = verify("calculate_triangle_area(base=1, height=2)", TRI, reference)
    assert v.label is None and v.invalid_reason == "reference_crash"


def test_tuple_result_compares_as_list():
    """Upstream exact match converts a top-level tuple to a list."""
    assert _normalize((1, 2)) == [1, 2]
    assert _normalize([(1, 2)]) == [(1, 2)]  # top level only, as upstream


# --- isolation ---------------------------------------------------------------

def test_mutating_function_cannot_touch_caller_or_reference():
    """polygon_area appends to its input list; each worker gets its own copy."""
    verts = [[1, 2], [3, 4], [5, 0]]
    call = ParsedCall("polygon_area", (), {"vertices": verts})
    first = execute(call)
    second = execute(call)
    assert first.status == second.status == "ok"
    assert first.value == second.value
    assert verts == [[1, 2], [3, 4], [5, 0]]


def test_worker_has_no_network():
    import multiprocessing as mp
    ctx = mp.get_context("spawn")
    recv, send = ctx.Pipe(duplex=False)
    p = ctx.Process(target=_probe_socket, args=(send,))
    p.start(); p.join(10)
    assert recv.recv() == "blocked"


def _probe_socket(conn):
    from agent_eval_gate.verifier import _disable_network
    _disable_network()
    import socket
    try:
        socket.create_connection(("127.0.0.1", 9))
        conn.send("open")
    except OSError:
        conn.send("blocked")


# --- development cases and upstream equivalence --------------------------------

@needs_data
def test_development_references_run_and_replay_identically():
    refs = load_references(DATA)
    dev = [c for c in load_case_inputs(DATA) if c.split is Split.DEVELOPMENT]
    assert len(dev) == 12
    for c in dev:
        a, b = run_reference(refs[c.case_id]), run_reference(refs[c.case_id])
        assert a.status == "ok", (c.case_id, a.error)
        assert a.value == b.value
        allowed = {f["name"] for f in c.functions}
        assert verify(refs[c.case_id].ground_truth[0], allowed, a).label == 1


@needs_data
def test_bundle_matches_the_functions_the_manifest_uses():
    names = {ast.parse(r.ground_truth[0], mode="eval").body.func.id
             for r in load_references(DATA).values()}
    assert names == set(FUNCTIONS)


@pytest.mark.skipif(not UPSTREAM.is_file(), reason="upstream source not fetched")
def test_bundle_bodies_equal_pinned_upstream():
    def defs(src):
        return {n.name: ast.dump(n) for n in ast.parse(src).body if isinstance(n, ast.FunctionDef)}
    upstream = defs(UPSTREAM.read_text())
    ours = defs(Path(bfcl_functions.__file__).read_text())
    assert set(ours) == set(FUNCTIONS)
    for name in ours:
        assert ours[name] == upstream[name], name
