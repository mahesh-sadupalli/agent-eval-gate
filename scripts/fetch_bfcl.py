"""Download the pinned BFCL exec_simple files into data/bfcl/<commit>/ and verify checksums.

Usage: uv run python scripts/fetch_bfcl.py
"""
from __future__ import annotations

import sys
import urllib.request
from pathlib import Path

from agent_eval_gate.bfcl import BFCL_COMMIT, SOURCES, sha256

BASE = (f"https://raw.githubusercontent.com/ShishirPatil/gorilla/{BFCL_COMMIT}"
        "/berkeley-function-call-leaderboard/data/")
OUT = Path(__file__).resolve().parents[1] / "data" / "bfcl" / BFCL_COMMIT


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    ok = True
    for upstream, (local, expected) in SOURCES.items():
        path = OUT / local
        if not path.is_file():
            with urllib.request.urlopen(BASE + upstream, timeout=60) as resp:
                path.write_bytes(resp.read())
        digest = sha256(path)
        status = "ok" if digest == expected else "CHECKSUM MISMATCH"
        ok &= digest == expected
        print(f"{status}  {local}  {digest}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
