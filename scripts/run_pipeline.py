"""Command-line entry point for the data pipeline.

Run from the project root:

    python scripts/run_pipeline.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Make the src-layout package importable without installing it.
SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from hk_mortality.pipeline import run_pipeline  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(run_pipeline())
