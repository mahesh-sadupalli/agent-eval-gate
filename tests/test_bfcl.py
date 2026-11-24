"""Manifest and loader tests for the pinned BFCL slice (PROTOCOL.md sections 2 and 7)."""
import json
import shutil
from dataclasses import fields
from pathlib import Path

import pytest

from agent_eval_gate import bfcl
from agent_eval_gate.bfcl import (
    ANSWERS_FILE,
    BFCL_COMMIT,
    MANIFEST,
    QUESTIONS_FILE,
    CaseInput,
    ManifestError,
    case_index,
    excluded_ids,
    load_case_inputs,
    load_references,
)
from agent_eval_gate.contract import Split

DATA = Path(__file__).resolve().parents[1] / "data" / "bfcl" / BFCL_COMMIT
needs_data = pytest.mark.skipif(not (DATA / QUESTIONS_FILE).is_file(),
                                reason="run scripts/fetch_bfcl.py first")


# --- manifest only (no data needed) -------------------------------------

def test_manifest_counts():
    index = case_index()
    assert len(index) == 60
    assert len(MANIFEST) == 26
    by_split = {s: sum(1 for _, sp in index.values() if sp is s) for s in Split}
    assert by_split == {Split.DEVELOPMENT: 12, Split.CALIBRATION: 22, Split.EVALUATION: 26}


def test_every_family_has_even_case_count():
    """Needed for the balanced AB/BA schedule (PROTOCOL.md section 3)."""
    assert all(len(ids) % 2 == 0 for _, ids in MANIFEST.values())


def test_duplicate_id_rejected(monkeypatch):
    bad = dict(MANIFEST, extra=(Split.EVALUATION, (0,)))
    monkeypatch.setattr(bfcl, "MANIFEST", bad)
    with pytest.raises(ManifestError, match="twice"):
        case_index()


def test_wrong_split_count_rejected(monkeypatch):
    bad = dict(MANIFEST)
    bad["book_room"] = (Split.CALIBRATION, bad["book_room"][1])
    monkeypatch.setattr(bfcl, "MANIFEST", bad)
    with pytest.raises(ManifestError, match="development"):
        case_index()


def test_agent_input_has_no_answer_fields():
    assert {f.name for f in fields(CaseInput)} == {
        "case_id", "family_id", "split", "question", "functions"}


# --- with the pinned data -----------------------------------------------

@needs_data
def test_loads_60_cases_with_schemas():
    cases = load_case_inputs(DATA)
    assert len(cases) == 60
    assert all(c.question and c.functions for c in cases)


@needs_data
def test_agent_inputs_contain_no_reference_calls():
    refs = load_references(DATA)
    for c in load_case_inputs(DATA):
        blob = json.dumps([c.question, c.functions])
        assert all(gt not in blob for gt in refs[c.case_id].ground_truth)


@needs_data
def test_references_are_exact_match():
    refs = load_references(DATA)
    assert len(refs) == 60
    assert all(r.execution_result_type == ["exact_match"] for r in refs.values())


@needs_data
def test_forty_source_cases_excluded():
    excluded = excluded_ids(DATA)
    assert len(excluded) == 40
    assert {"exec_simple_24", "exec_simple_25"} <= set(excluded)  # estimate_derivative


@needs_data
def test_tampered_file_stops_the_run(tmp_path):
    shutil.copy(DATA / QUESTIONS_FILE, tmp_path / QUESTIONS_FILE)
    with open(tmp_path / QUESTIONS_FILE, "a") as f:
        f.write(" ")
    with pytest.raises(ManifestError, match="checksum"):
        load_case_inputs(tmp_path)


def test_missing_file_stops_the_run(tmp_path):
    with pytest.raises(ManifestError, match="missing"):
        load_references(tmp_path)
