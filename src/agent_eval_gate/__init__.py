"""Agent Eval Gate — a ship decision that is only as confident as its judge deserves.

Read README.md for the plain-language introduction. The frozen interface
between the harness and the gate lives in `contract`.
"""
from agent_eval_gate.contract import (
    GROUND_TRUTH_TOL,
    CaseResult,
    GateConfig,
    GateInput,
    GateOutput,
    JudgeReliability,
    Position,
    VariantSpec,
    Verdict,
)

__all__ = [
    "GROUND_TRUTH_TOL",
    "CaseResult",
    "GateConfig",
    "GateInput",
    "GateOutput",
    "JudgeReliability",
    "Position",
    "VariantSpec",
    "Verdict",
]

__version__ = "0.0.1"
