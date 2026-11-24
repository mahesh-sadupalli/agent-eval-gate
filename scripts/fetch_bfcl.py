"""Download the pinned BFCL exec_simple files into data/bfcl/<commit>/ and verify checksums.

Also fetches the upstream function/checker source (data/bfcl/<commit>/upstream_src/)
used by tests/test_verifier.py to check the vendored function bodies.

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

REPO = f"https://raw.githubusercontent.com/ShishirPatil/gorilla/{BFCL_COMMIT}/"
_EXEC = "berkeley-function-call-leaderboard/bfcl/eval_checker/executable_eval/"
UPSTREAM_SRC = {
    _EXEC + "executable_python_function.py": (
        "upstream_src/executable_python_function.py",
        "43f387b3cfbcd54d0bcb0d1ddeb8f7f53e17aaa64ddd9950840ec1d2b42d3410"),
    _EXEC + "executable_checker.py": (
        "upstream_src/executable_checker.py",
        "e41a82a34590f95bc2d1c8c39863b4232f8c018be379b9b1b5a6177c10127554"),
}


def main() -> int:
    ok = True
    files = [(BASE + u, loc, h) for u, (loc, h) in SOURCES.items()]
    files += [(REPO + u, loc, h) for u, (loc, h) in UPSTREAM_SRC.items()]
    for url, local, expected in files:
        path = OUT / local
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.is_file():
            with urllib.request.urlopen(url, timeout=60) as resp:
                path.write_bytes(resp.read())
        digest = sha256(path)
        status = "ok" if digest == expected else "CHECKSUM MISMATCH"
        ok &= digest == expected
        print(f"{status}  {local}  {digest}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
