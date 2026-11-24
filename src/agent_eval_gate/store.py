"""Append-only run records with resume (PROTOCOL.md section 6, M1 Q6 and Q7).

A run lives in runs/<run_id>/ where run_id is a hash of the frozen config, so a
changed model, prompt, verifier, seed, or manifest is automatically a new run.
Records are JSON lines, one per completed unit of work, written and fsynced as
they finish. Accepted records are never overwritten; only transport failures
may be followed by a later record for the same key.

Checksums and hashes support replay and accidental-change detection. They do
not prove records were not fabricated.
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
from enum import Enum
from pathlib import Path
from typing import Any

from agent_eval_gate import bfcl
from agent_eval_gate.contract import PROTOCOL_VERSION, Position
from agent_eval_gate.judge import JUDGE_MODEL, JUDGE_PROMPT, POSITION_SEED, RUBRIC_ID, JudgeRecord
from agent_eval_gate.runner import (
    ARM_ORDER_SEED,
    BASELINE_PROMPT,
    CANDIDATE_PROMPT,
    ArmRecord,
    Attempt,
    ProviderResponse,
    sha256_text,
)
from agent_eval_gate.verifier import VERIFIER_VERSION, Verification

ARMS_FILE = "arms.jsonl"
JUDGE_FILE = "judge.jsonl"
CONFIG_FILE = "config.json"
SESSIONS_FILE = "sessions.jsonl"


def default_config(agent_model: str, judge_model: str = JUDGE_MODEL) -> dict:
    """Everything that, if changed, must start a new run."""
    return {
        "protocol_version": PROTOCOL_VERSION,
        "bfcl_commit": bfcl.BFCL_COMMIT,
        "source_sha256": {local: h for local, h in bfcl.SOURCES.values()},
        "manifest": {fam: [sp.value, list(ids)] for fam, (sp, ids) in bfcl.MANIFEST.items()},
        "agent_model": agent_model,
        "judge_model": judge_model,
        "baseline_prompt_sha256": sha256_text(BASELINE_PROMPT),
        "candidate_prompt_sha256": sha256_text(CANDIDATE_PROMPT),
        "judge_prompt_sha256": sha256_text(JUDGE_PROMPT),
        "rubric_id": RUBRIC_ID,
        "verifier_version": VERIFIER_VERSION,
        "arm_order_seed": ARM_ORDER_SEED,
        "position_seed": POSITION_SEED,
        "agent_decoding": {"temperature": 0.0, "top_p": 1.0, "max_tokens": 2048},
        "judge_decoding": {"temperature": 0.0, "top_p": 1.0, "max_tokens": 512},
    }


def config_hash(config: dict) -> str:
    return hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()


def environment() -> dict:
    """Recorded per session; not part of the run id."""
    def git(*args: str) -> str:
        try:
            return subprocess.run(["git", *args], capture_output=True, text=True,
                                  cwd=Path(__file__).parent, timeout=10).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            return ""
    diff = git("diff", "HEAD")
    return {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "git_revision": git("rev-parse", "HEAD"),
        "git_dirty_patch_sha256": hashlib.sha256(diff.encode()).hexdigest() if diff else "",
        "started": time.time(),
    }


def _jsonable(obj: Any) -> Any:
    if dataclasses.is_dataclass(obj):
        return {f.name: _jsonable(getattr(obj, f.name)) for f in dataclasses.fields(obj)}
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, dict):
        return {(k.value if isinstance(k, Enum) else str(k)): _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(v) for v in obj]
    return obj


def _response(d: dict | None) -> ProviderResponse | None:
    return None if d is None else ProviderResponse(**d)


def arm_from_dict(d: dict) -> ArmRecord:
    return ArmRecord(d["arm"], d["request"], tuple(Attempt(**a) for a in d["attempts"]),
                     _response(d["response"]), Verification(**d["verification"]))


def judge_from_dict(d: dict) -> JudgeRecord:
    return JudgeRecord(d["case_id"], Position(d["position"]), d["request"],
                       tuple(Attempt(**a) for a in d["attempts"]), _response(d["response"]),
                       d["p_baseline"], d["p_candidate"], d["error"])


def arm_accepted(rec: ArmRecord) -> bool:
    return rec.verification.invalid_reason != "transport_failed"


def judge_accepted(rec: JudgeRecord) -> bool:
    return rec.error not in ("transport_failed", "arm_missing")


class RunStore:
    def __init__(self, root: Path, config: dict, log_session: bool = True):
        self.config = config
        self.run_id = config_hash(config)[:16]
        self.dir = Path(root) / self.run_id
        self.dir.mkdir(parents=True, exist_ok=True)
        cfg_path = self.dir / CONFIG_FILE
        if cfg_path.exists():
            if json.loads(cfg_path.read_text()) != config:
                raise RuntimeError(f"{cfg_path} differs from the requested config")
        else:
            cfg_path.write_text(json.dumps(config, indent=2, sort_keys=True))
        if log_session:
            self._append(SESSIONS_FILE, environment())

    @classmethod
    def open(cls, run_dir: Path) -> "RunStore":
        """Reopen a saved run read-only; its config must still hash to its directory name."""
        run_dir = Path(run_dir)
        config = json.loads((run_dir / CONFIG_FILE).read_text())
        if config_hash(config)[:16] != run_dir.name:
            raise RuntimeError(f"{run_dir}: config does not match run id")
        return cls(run_dir.parent, config, log_session=False)

    def _append(self, name: str, row: dict) -> None:
        with open(self.dir / name, "a", encoding="utf-8") as f:
            f.write(json.dumps(_jsonable(row), sort_keys=True, default=repr) + "\n")
            f.flush()
            os.fsync(f.fileno())

    def _rows(self, name: str) -> list[dict]:
        path = self.dir / name
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]

    # --- arms -------------------------------------------------------------------
    def arms(self) -> dict[tuple[str, str], ArmRecord]:
        """Latest record per (case, arm). An accepted record is always the last one."""
        return {(r["case_id"], r["record"]["arm"]): arm_from_dict(r["record"])
                for r in self._rows(ARMS_FILE)}

    def write_arm(self, case_id: str, rec: ArmRecord) -> None:
        prev = self.arms().get((case_id, rec.arm))
        if prev is not None and arm_accepted(prev):
            raise RuntimeError(f"accepted record exists for {case_id}/{rec.arm}")
        self._append(ARMS_FILE, {"run_id": self.run_id, "case_id": case_id, "record": rec})

    # --- judge ---------------------------------------------------------------------
    def judgments(self) -> dict[str, JudgeRecord]:
        return {r["case_id"]: judge_from_dict(r["record"]) for r in self._rows(JUDGE_FILE)}

    def write_judgment(self, rec: JudgeRecord) -> None:
        prev = self.judgments().get(rec.case_id)
        if prev is not None and judge_accepted(prev):
            raise RuntimeError(f"accepted judgment exists for {rec.case_id}")
        self._append(JUDGE_FILE, {"run_id": self.run_id, "case_id": rec.case_id, "record": rec})
