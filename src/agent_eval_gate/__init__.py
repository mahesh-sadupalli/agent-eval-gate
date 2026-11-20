"""Agent Eval Gate — a release decision that is only as confident as its judge deserves.

Read README.md for the plain-language introduction. The interface between
the harness and the gate lives in `contract`.
"""
from agent_eval_gate.contract import (
    PROTOCOL_VERSION,
    CalibrationReport,
    CaseResult,
    GateConfig,
    GateInput,
    GateOutput,
    MethodId,
    Position,
    Split,
    Stratum,
    StratumDiagnostic,
    UnresolvedReason,
    VariantSpec,
    Verdict,
)

__all__ = [
    "PROTOCOL_VERSION",
    "CalibrationReport",
    "CaseResult",
    "GateConfig",
    "GateInput",
    "GateOutput",
    "MethodId",
    "Position",
    "Split",
    "Stratum",
    "StratumDiagnostic",
    "UnresolvedReason",
    "VariantSpec",
    "Verdict",
]

__version__ = "0.0.1"
