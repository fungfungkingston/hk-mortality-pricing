"""Record data provenance: source URLs, retrieval date, selected sheets, and
a SHA-256 checksum of the downloaded workbook.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from . import config


def sha256_file(path: Path) -> str:
    """Return the SHA-256 hex digest of a file."""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_provenance(
    path: Path | str | None = None,
    *,
    retrieval_date: str | None = None,
) -> dict:
    """Write the data-provenance JSON and return its contents."""
    path = Path(path) if path else config.RAW_WORKBOOK
    retrieval_date = retrieval_date or datetime.now(timezone.utc).isoformat()

    # Store the local path relative to the project root so the provenance file
    # stays portable and contains no machine-specific absolute paths.
    try:
        local_file = str(path.resolve().relative_to(config.PROJECT_ROOT.resolve()))
    except ValueError:
        local_file = str(path)

    provenance = {
        "source_title": config.SOURCE_TITLE,
        "publisher": config.PUBLISHER,
        "source_workbook_url": config.SOURCE_WORKBOOK_URL,
        "source_pdf_url": config.SOURCE_PDF_URL,
        "retrieval_date_utc": retrieval_date,
        "local_file": local_file,
        "sha256": sha256_file(path),
        "selected_sheets": [
            {"sheet_title": title, "reference_year": year, "sex": sex}
            for title, (year, sex) in config.SHEET_MAP.items()
        ],
    }

    config.PROVENANCE_JSON.parent.mkdir(parents=True, exist_ok=True)
    config.PROVENANCE_JSON.write_text(
        json.dumps(provenance, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return provenance
