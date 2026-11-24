"""Report and replay tests on a fake development run (no paid calls).

Fake design: baseline always returns the reference call (pass), candidate a call
with no arguments (fail), and the judge always says {"p_A": 0.8, "p_B": 0.3}.
So every case has D = -1, J = -0.5 under AB and +0.5 under BA, and AB/BA is
balanced within each family, giving J_f = 0 and residual D_f - J_f = -1.
"""
import json
from pathlib import Path

import pytest

from agent_eval_gate.bfcl import BFCL_COMMIT, QUESTIONS_FILE, load_case_inputs, load_references
from agent_eval_gate.collect import CallBudget, collect
from agent_eval_gate.contract import Split
from agent_eval_gate.report import REPORT_FILE, main, replay, write_report
from agent_eval_gate.runner import BASELINE_PROMPT, CANDIDATE_PROMPT, make_variant
from agent_eval_gate.store import ARMS_FILE, JUDGE_FILE, SESSIONS_FILE, RunStore, default_config
from fakes import Agent, Judge, no_sleep

DATA = Path(__file__).resolve().parents[1] / "data" / "bfcl" / BFCL_COMMIT
pytestmark = pytest.mark.skipif(not (DATA / QUESTIONS_FILE).is_file(),
                                reason="run scripts/fetch_bfcl.py first")


@pytest.fixture
def run(tmp_path):
    cases = [c for c in load_case_inputs(DATA) if c.split is Split.DEVELOPMENT]
    refs = load_references(DATA)
    model = "fake-agent-2026-01-01"
    store = RunStore(tmp_path, default_config(model))
    collect(cases, refs, Agent(cases, refs), Judge(), store,
            make_variant(model, BASELINE_PROMPT, cases), make_variant(model, CANDIDATE_PROMPT, cases),
            CallBudget(1000), sleep=no_sleep)
    return store


def test_report_numbers_match_the_fake_design(run):
    r = write_report(run)
    assert r["counts"] == {"cases_with_records": 12, "complete_pairs": 12, "invalid_measurements": 0,
                           "missing_judgments": 0, "families": 4}
    assert r["success_rate"] == {"baseline": 1, "candidate": 0}
    assert r["verified_delta"] == {"case_weighted": -1, "family_weighted": -1}
    assert r["judge_delta"]["family_weighted"] == pytest.approx(0.0)
    assert r["calibration"]["residual_mean"] == pytest.approx(-1.0)
    assert r["position"]["AB"] == {"n": 6, "mean_judge_delta": pytest.approx(-0.5)}
    assert r["position"]["BA"] == {"n": 6, "mean_judge_delta": pytest.approx(0.5)}
    strata = r["calibration"]["strata"]
    assert strata["baseline_only_pass"]["n_cases"] == 12
    assert strata["both_pass"] == {"n_cases": 0, "mean_judge_delta": None, "mean_residual": None}
    assert r["calls"]["agent_attempts"] == 24 and r["calls"]["judge_attempts"] == 12


def test_empty_stratum_is_reported_as_empty_not_zero(run):
    both_fail = write_report(run)["calibration"]["strata"]["both_fail"]
    assert both_fail["n_cases"] == 0 and both_fail["mean_judge_delta"] is None


def test_replay_reproduces_report_without_mismatches(run):
    saved = write_report(run)
    mismatches, rebuilt = replay(RunStore.open(run.dir), DATA)
    assert mismatches == []
    assert json.loads(json.dumps(rebuilt)) == saved


def test_replay_is_read_only(run):
    write_report(run)
    before = {p.name: p.read_bytes() for p in run.dir.iterdir()}
    replay(RunStore.open(run.dir), DATA)
    assert {p.name: p.read_bytes() for p in run.dir.iterdir()} == before


def test_replay_detects_altered_agent_response(run):
    path = run.dir / ARMS_FILE
    rows = [json.loads(x) for x in path.read_text().splitlines()]
    target = next(r for r in rows if r["record"]["arm"] == "candidate")
    name = target["record"]["response"]["text"].rstrip("()")
    base = next(r for r in rows if r["case_id"] == target["case_id"] and r["record"]["arm"] == "baseline")
    target["record"]["response"]["text"] = base["record"]["response"]["text"]   # now a correct call
    assert name
    path.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in rows))
    mismatches, _ = replay(RunStore.open(run.dir), DATA)
    assert any(target["case_id"] in m and "candidate" in m for m in mismatches)


def test_replay_detects_altered_judge_output(run):
    path = run.dir / JUDGE_FILE
    rows = [json.loads(x) for x in path.read_text().splitlines()]
    rows[0]["record"]["response"]["text"] = '{"p_A": 0.1, "p_B": 0.1}'
    path.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in rows))
    mismatches, _ = replay(RunStore.open(run.dir), DATA)
    assert any("judge" in m for m in mismatches)


def test_replay_detects_edited_report(run):
    write_report(run)
    (run.dir / REPORT_FILE).write_text(json.dumps({"tampered": True}))
    mismatches, _ = replay(RunStore.open(run.dir), DATA)
    assert "report.json differs" in mismatches[-1]


def test_open_rejects_renamed_run_dir(run, tmp_path):
    moved = run.dir.parent / "0000000000000000"
    run.dir.rename(moved)
    with pytest.raises(RuntimeError, match="run id"):
        RunStore.open(moved)


def test_cli_report_and_replay(run, capsys):
    assert main([str(run.dir)]) == 0
    assert (run.dir / REPORT_FILE).exists()
    assert main([str(run.dir), "--replay", "--data", str(DATA)]) == 0
    assert '"complete_pairs": 12' in capsys.readouterr().out
    assert (run.dir / SESSIONS_FILE).read_text().count("\n") == 1   # only the collecting session
