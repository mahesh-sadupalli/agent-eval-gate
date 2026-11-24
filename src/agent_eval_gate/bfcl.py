"""Pinned BFCL exec_simple slice and its split manifest (PROTOCOL.md sections 2 and 7).

Agent-facing data (question + tool schema) and verifier-only data (reference
calls) are loaded by separate functions so they never travel together. Every
load checks the source checksum and the manifest first; a failure stops the run.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from agent_eval_gate.contract import Split

BFCL_COMMIT = "4d05b53fce8a2055957311817f6c7f9143acdc11"
QUESTIONS_FILE = "BFCL_v3_exec_simple.json"
ANSWERS_FILE = "possible_answer_BFCL_v3_exec_simple.json"

#: Upstream path (under berkeley-function-call-leaderboard/data/) -> local name, sha256.
SOURCES = {
    "BFCL_v3_exec_simple.json":
        (QUESTIONS_FILE, "32ee3959e8e3f92fac1e90e55bf5fa41c759bfef4e6a2d88421af527a859d0a4"),
    "possible_answer/BFCL_v3_exec_simple.json":
        (ANSWERS_FILE, "4584017c92ae9a2407eac25bcec2496233a32a08182301b15f65538aa575b5a7"),
}

N_SOURCE_CASES = 100

# PROTOCOL.md section 7, authoritative for replay. Family -> (split, ID suffixes).
_D, _C, _E = Split.DEVELOPMENT, Split.CALIBRATION, Split.EVALUATION
MANIFEST: dict[str, tuple[Split, tuple[int, ...]]] = {
    "combinatorics": (_D, (0, 1, 16, 17, 64, 65)),
    "book_room": (_D, (90, 91)),
    "add_binary_numbers": (_D, (80, 81)),
    "calculate_triangle_area": (_D, (20, 21)),
    "mean_and_deviation": (_C, (14, 15, 18, 19)),
    "calculate_investment_value": (_C, (86, 87)),
    "order_food": (_C, (92, 93)),
    "sort_array": (_C, (78, 79)),
    "mortgage_calculator": (_C, (70, 71)),
    "calculate_electrostatic_potential_energy": (_C, (8, 9)),
    "calculate_future_value": (_C, (12, 13)),
    "linear_regression": (_C, (82, 83)),
    "get_fibonacci_sequence": (_C, (42, 43)),
    "calculate_cosine_similarity": (_C, (2, 3)),
    "polygon_area": (_E, (98, 99)),
    "maxPoints": (_E, (84, 85)),
    "quadratic_roots": (_E, (72, 73)),
    "calculate_density": (_E, (4, 5)),
    "geometry_area_circle": (_E, (28, 29)),
    "calculate_displacement": (_E, (6, 7)),
    "calculate_final_velocity": (_E, (10, 11)),
    "calculate_nutritional_needs": (_E, (88, 89)),
    "gcd_and_lcm": (_E, (66, 67, 68, 69)),
    "get_prime_factors": (_E, (46, 47)),
    "mat_mul": (_E, (62, 63)),
    "get_distance": (_E, (40, 41)),
}

#: Expected (families, cases) per split.
EXPECTED_COUNTS = {_D: (4, 12), _C: (10, 22), _E: (12, 26)}


class ManifestError(ValueError):
    """The data or manifest does not match the frozen protocol."""


@dataclass(frozen=True)
class CaseInput:
    """What an agent (and the judge) may see for one case."""
    case_id: str
    family_id: str
    split: Split
    question: list          # BFCL chat turns, unmodified
    functions: list         # tool schemas, unmodified


@dataclass(frozen=True)
class Reference:
    """Verifier-only: the reference call(s) for one case."""
    case_id: str
    ground_truth: list[str]
    execution_result_type: list[str]


def case_index() -> dict[str, tuple[str, Split]]:
    """case_id -> (family_id, split), after validating the manifest itself."""
    index: dict[str, tuple[str, Split]] = {}
    for family, (split, suffixes) in MANIFEST.items():
        for s in suffixes:
            cid = f"exec_simple_{s}"
            if cid in index:
                raise ManifestError(f"{cid} listed twice")
            index[cid] = (family, split)
    for split, (n_fam, n_case) in EXPECTED_COUNTS.items():
        fams = [f for f, (sp, _) in MANIFEST.items() if sp is split]
        cases = [c for c, (_, sp) in index.items() if sp is split]
        if (len(fams), len(cases)) != (n_fam, n_case):
            raise ManifestError(
                f"{split.value}: {len(fams)} families / {len(cases)} cases, "
                f"expected {n_fam} / {n_case}")
    return index


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_verified(data_dir: Path, name: str) -> dict[str, dict]:
    expected = {local: digest for local, digest in SOURCES.values()}[name]
    path = data_dir / name
    if not path.is_file():
        raise ManifestError(f"missing {path}; run scripts/fetch_bfcl.py")
    if sha256(path) != expected:
        raise ManifestError(f"checksum mismatch for {path}")
    rows: dict[str, dict] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            if row["id"] in rows:
                raise ManifestError(f"duplicate id {row['id']} in {name}")
            rows[row["id"]] = row
    if len(rows) != N_SOURCE_CASES:
        raise ManifestError(f"{name}: {len(rows)} cases, expected {N_SOURCE_CASES}")
    return rows


def _select(rows: dict[str, dict], name: str) -> list[tuple[str, str, Split, dict]]:
    index = case_index()
    missing = sorted(set(index) - set(rows))
    if missing:
        raise ManifestError(f"{name} lacks manifest ids {missing}")
    return [(cid, fam, sp, rows[cid]) for cid, (fam, sp) in index.items()]


def load_case_inputs(data_dir: Path) -> list[CaseInput]:
    """Agent-facing data for the 60 manifest cases. Contains no answers."""
    rows = _read_verified(data_dir, QUESTIONS_FILE)
    return [CaseInput(cid, fam, sp, row["question"], row["function"])
            for cid, fam, sp, row in _select(rows, QUESTIONS_FILE)]


def load_references(data_dir: Path) -> dict[str, Reference]:
    """Verifier-only references for the 60 manifest cases; all must be exact-match."""
    rows = _read_verified(data_dir, ANSWERS_FILE)
    refs: dict[str, Reference] = {}
    for cid, _, _, row in _select(rows, ANSWERS_FILE):
        if row["execution_result_type"] != ["exact_match"]:
            raise ManifestError(f"{cid}: check type {row['execution_result_type']}, "
                                "expected ['exact_match']")
        refs[cid] = Reference(cid, row["ground_truth"], row["execution_result_type"])
    return refs


def excluded_ids(data_dir: Path) -> list[str]:
    """Source cases outside the manifest (38 remote-service + 2 code-string)."""
    rows = _read_verified(data_dir, QUESTIONS_FILE)
    return sorted(set(rows) - set(case_index()), key=lambda c: int(c.rsplit("_", 1)[1]))
