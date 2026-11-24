"""Calibration report and replay for a saved run (PROTOCOL.md section 4, M1 Q6 and Q9).

The report is descriptive: counts, success rates, paired and family means,
the four outcome strata, position diagnostics, missingness, and calls. It
makes no release decision; that is M2.

Replay re-executes the references, re-verifies every saved agent response,
re-parses every saved judge response, and rebuilds the report from the
records alone. Any difference from what was recorded is listed.

Usage: uv run python -m agent_eval_gate.report runs/<run_id> [--replay]
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from statistics import mean

from agent_eval_gate import bfcl
from agent_eval_gate.contract import CalibrationReport, CaseResult, Position, Stratum, StratumDiagnostic
from agent_eval_gate.judge import JudgeParseError, parse_scores, to_case_result
from agent_eval_gate.runner import PairRecord
from agent_eval_gate.store import RunStore, _jsonable
from agent_eval_gate.verifier import run_reference, verify

REPORT_FILE = "report.json"
SAMPLING_DESIGN = "simple random partition of 22 study families (PROTOCOL.md section 5)"


def _m(xs: list[float]) -> float | None:
    return mean(xs) if xs else None


def case_results(store: RunStore) -> list[CaseResult]:
    """One contract record per case that has both arms and a judgment."""
    index = bfcl.case_index()
    arms, judged = store.arms(), store.judgments()
    out = []
    for cid in sorted(judged, key=lambda c: int(c.rsplit("_", 1)[1])):
        b, c = arms.get((cid, "baseline")), arms.get((cid, "candidate"))
        if b is None or c is None:
            continue
        fam, split = index[cid]
        pair = PairRecord(cid, fam, "", b, c)
        out.append(to_case_result(pair, judged[cid], split, store.run_id,
                                  store.config["judge_model"]))
    return out


def summarize(store: RunStore) -> dict:
    results = case_results(store)
    arms = store.arms()
    complete = [r for r in results if r.verified_delta is not None and r.judge_delta is not None]

    fam_d, fam_j = defaultdict(list), defaultdict(list)
    for r in complete:
        fam_d[r.family_id].append(r.verified_delta)
        fam_j[r.family_id].append(r.judge_delta)
    families = sorted(fam_d)
    d_f = {f: mean(fam_d[f]) for f in families}
    j_f = {f: mean(fam_j[f]) for f in families}

    strata = {}
    for s in Stratum:
        rs = [r for r in complete if r.stratum is s]
        strata[s] = StratumDiagnostic(
            len(rs), _m([r.judge_delta for r in rs]),
            _m([r.verified_delta - r.judge_delta for r in rs]))

    calibration = CalibrationReport(
        run_id=store.run_id,
        judge_version=f"{store.config['judge_model']}/{store.config['rubric_id']}",
        sampling_design=SAMPLING_DESIGN,
        n_families=len(families),
        n_cases=len(complete),
        n_invalid=sum(r.is_measurement_invalid for r in results),
        residual_mean=_m([d_f[f] - j_f[f] for f in families]),
        strata=strata,
    )
    valid_b = [r.baseline_verified for r in results if r.baseline_verified is not None]
    valid_c = [r.candidate_verified for r in results if r.candidate_verified is not None]
    attempts = [a for rec in arms.values() for a in rec.attempts]
    judge_attempts = [a for rec in store.judgments().values() for a in rec.attempts]
    usage = defaultdict(int)
    for rec in [*arms.values(), *store.judgments().values()]:
        if rec.response is not None:
            for k, v in rec.response.usage.items():
                if isinstance(v, int):
                    usage[k] += v

    return {
        "run_id": store.run_id,
        "note": "Descriptive calibration diagnostics. No release decision (M2).",
        "counts": {
            "cases_with_records": len(results),
            "complete_pairs": len(complete),
            "invalid_measurements": calibration.n_invalid,
            "missing_judgments": sum(r.judge_delta is None for r in results),
            "families": len(families),
        },
        "success_rate": {"baseline": _m(valid_b), "candidate": _m(valid_c)},
        "verified_delta": {"case_weighted": _m([r.verified_delta for r in complete]),
                           "family_weighted": _m(list(d_f.values()))},
        "judge_delta": {"case_weighted": _m([r.judge_delta for r in complete]),
                        "family_weighted": _m(list(j_f.values()))},
        "calibration": _jsonable(calibration),
        "position": {p.value: {"n": len(rs := [r for r in complete if r.position is p]),
                               "mean_judge_delta": _m([r.judge_delta for r in rs])}
                     for p in Position},
        "families": {f: {"n": len(fam_d[f]), "D_f": d_f[f], "J_f": j_f[f]} for f in families},
        "calls": {"agent_attempts": len(attempts),
                  "agent_retries": sum(bool(a.error) for a in attempts),
                  "judge_attempts": len(judge_attempts),
                  "judge_retries": sum(bool(a.error) for a in judge_attempts),
                  "agent_seconds": sum(a.seconds for a in attempts),
                  "judge_seconds": sum(a.seconds for a in judge_attempts),
                  "usage": dict(usage)},
    }


def write_report(store: RunStore) -> dict:
    report = summarize(store)
    (store.dir / REPORT_FILE).write_text(json.dumps(report, indent=2, sort_keys=True))
    return report


def replay(store: RunStore, data_dir: Path) -> tuple[list[str], dict]:
    """Recompute verification, judge parsing, and the report from saved records."""
    refs = bfcl.load_references(data_dir)
    schemas = {c.case_id: {f["name"] for f in c.functions} for c in bfcl.load_case_inputs(data_dir)}
    mismatches: list[str] = []
    reference_cache = {}
    for (cid, arm), rec in sorted(store.arms().items()):
        if rec.response is None:
            continue
        if cid not in reference_cache:
            reference_cache[cid] = run_reference(refs[cid])
        again = verify(rec.response.text, schemas[cid], reference_cache[cid])
        if (again.status, again.reason) != (rec.verification.status, rec.verification.reason):
            mismatches.append(f"{cid}/{arm}: recorded {rec.verification.status}/"
                              f"{rec.verification.reason}, replay {again.status}/{again.reason}")
    for cid, rec in sorted(store.judgments().items()):
        if rec.response is None:
            continue
        try:
            p_a, p_b = parse_scores(rec.response.text)
            p = (p_a, p_b) if rec.position is Position.AB else (p_b, p_a)
        except JudgeParseError:
            p = (None, None)
        if p != (rec.p_baseline, rec.p_candidate):
            mismatches.append(f"{cid}/judge: recorded {(rec.p_baseline, rec.p_candidate)}, replay {p}")
    report = summarize(store)
    saved = store.dir / REPORT_FILE
    if saved.exists() and json.loads(saved.read_text()) != json.loads(json.dumps(report)):
        mismatches.append("report.json differs from the report rebuilt from records")
    return mismatches, report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("run_dir", type=Path)
    ap.add_argument("--replay", action="store_true", help="re-verify records and compare")
    ap.add_argument("--data", type=Path,
                    default=Path(__file__).resolve().parents[2] / "data" / "bfcl" / bfcl.BFCL_COMMIT)
    args = ap.parse_args(argv)
    store = RunStore.open(args.run_dir)
    if args.replay:
        mismatches, report = replay(store, args.data)
        print(json.dumps(report, indent=2, sort_keys=True))
        for m in mismatches:
            print("MISMATCH", m, file=sys.stderr)
        return 1 if mismatches else 0
    print(json.dumps(write_report(store), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
