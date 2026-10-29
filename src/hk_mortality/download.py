"""Download (or locate) the official source workbook.

This module never fabricates data.  If the workbook is already present locally
it is used as-is; otherwise it is fetched from the official URL.  If the fetch
fails, the exception is surfaced so the caller can fall back to the manual
download path described in the README.
"""

from __future__ import annotations

import urllib.request
from pathlib import Path

from . import config


def ensure_raw_workbook() -> Path:
    """Return the path to the raw workbook, downloading it if missing."""
    path = config.RAW_WORKBOOK
    if path.exists():
        return path

    config.RAW_DIR.mkdir(parents=True, exist_ok=True)
    partial = path.with_suffix(".part")
    try:
        urllib.request.urlretrieve(config.SOURCE_WORKBOOK_URL, partial)
        partial.replace(path)
    finally:
        if partial.exists():
            partial.unlink(missing_ok=True)
    return path
