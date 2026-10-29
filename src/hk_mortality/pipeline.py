"""End-to-end pipeline: locate workbook -> extract -> validate -> save.

This is the single entry point for the data stage of the project.
"""

from __future__ import annotations

from . import config
from .download import ensure_raw_workbook
from .extract import extract_tidy, summarize_sheets
from .provenance import write_provenance
from .validate import validate


def run_pipeline() -> int:
    raw = ensure_raw_workbook()

    tidy = extract_tidy(raw)
    report = validate(tidy)

    config.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    tidy.to_csv(config.TIDY_CSV, index=False)
    provenance = write_provenance(raw)

    # ------------------------------------------------------------------ #
    # Human-readable report
    # ------------------------------------------------------------------ #
    print("Selected sheets:")
    for sheet in summarize_sheets(raw):
        print(
            f"  {sheet.sheet_title!r} -> ({sheet.reference_year}, {sheet.sex}) "
            f"rows={sheet.n_rows} ages={sheet.age_min}..{sheet.age_max}"
        )

    print(f"\nTotal tidy rows: {len(tidy)}")
    print(f"Tidy CSV:        {config.TIDY_CSV}")
    print(f"Provenance:      {config.PROVENANCE_JSON}")
    print(f"SHA-256:         {provenance['sha256']}")

    print("\nSample rows (head):")
    print(tidy.head(8).to_string(index=False))
    print("...")
    print(tidy.tail(8).to_string(index=False))

    print("\nValidation:")
    if report.errors:
        print("  ERRORS:")
        for item in report.errors:
            print(f"    - {item}")
    if report.warnings:
        print("  WARNINGS:")
        for item in report.warnings:
            print(f"    - {item}")
    if report.ok and not report.warnings:
        print("  OK: no errors or warnings.")

    return 0 if report.ok else 1
