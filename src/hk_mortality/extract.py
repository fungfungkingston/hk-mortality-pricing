"""Extract the historical life tables from the official workbook.

The workbook layout (observed, not assumed) is:

  row 1-2 : title (Chinese / English)
  row 3   : blank
  row 4   : column heading block (Chinese + English)
  row 5   : machine-friendly column names  x, q(x), l(x), d(x), L(x), T(x), e(x)
  row 6.. : data rows, one per age, x = 0..99
  ...     : a terminal row '100+' (age string, not an integer) and footnotes

We identify a table's data region by its header row (x, q(x), ...) and read
rows whose first cell is an integer age.  The '100+' row is deliberately
skipped because it is not an integer age and carries qx = 1 (terminal).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import openpyxl
import pandas as pd

from . import config


@dataclass(frozen=True)
class SheetResult:
    """Summary of one extracted sheet, used for reporting."""

    sheet_title: str
    reference_year: int
    sex: str
    n_rows: int
    age_min: int
    age_max: int


def _read_rows(path: Path, sheet_title: str) -> list[tuple]:
    """Read all cell values (as tuples) from a single sheet."""
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        ws = wb[sheet_title]
        return list(ws.iter_rows(values_only=True))
    finally:
        wb.close()


def _find_header_index(rows: list[tuple]) -> int:
    """Return the index of the header row whose first two cells are (x, q(x))."""
    for i, row in enumerate(rows):
        if row and row[0] == "x" and row[1] == "q(x)":
            return i
    raise ValueError("could not find header row (x, q(x), ...) in sheet")


def _parse_sheet(rows: list[tuple]) -> list[tuple[int, float, int]]:
    """Parse (age, qx, lx) records from the rows below the header row."""
    header = _find_header_index(rows)
    records: list[tuple[int, float, int]] = []
    for row in rows[header + 1 :]:
        if row and isinstance(row[0], int) and row[1] is not None and row[2] is not None:
            records.append((row[0], float(row[1]), int(row[2])))
    return records


def extract_tidy(path: Path | str | None = None) -> pd.DataFrame:
    """Extract all selected sheets and return a tidy DataFrame.

    Columns: reference_year, sex, age, qx, lx.
    Source values are preserved without rounding; lx is kept as an integer.
    """
    path = Path(path) if path else config.RAW_WORKBOOK
    frames: list[pd.DataFrame] = []
    for sheet_title, (year, sex) in config.SHEET_MAP.items():
        records = _parse_sheet(_read_rows(path, sheet_title))
        frame = pd.DataFrame(records, columns=["age", "qx", "lx"])
        frame.insert(0, "sex", sex)
        frame.insert(0, "reference_year", year)
        frames.append(frame)

    tidy = pd.concat(frames, ignore_index=True)
    tidy = tidy[config.TIDY_COLUMNS]
    tidy = tidy.sort_values(["reference_year", "sex", "age"]).reset_index(drop=True)
    return tidy


def summarize_sheets(path: Path | str | None = None) -> list[SheetResult]:
    """Return a per-sheet summary for reporting."""
    path = Path(path) if path else config.RAW_WORKBOOK
    results: list[SheetResult] = []
    for sheet_title, (year, sex) in config.SHEET_MAP.items():
        records = _parse_sheet(_read_rows(path, sheet_title))
        ages = [age for age, _, _ in records]
        results.append(
            SheetResult(
                sheet_title=sheet_title,
                reference_year=year,
                sex=sex,
                n_rows=len(records),
                age_min=min(ages),
                age_max=max(ages),
            )
        )
    return results
