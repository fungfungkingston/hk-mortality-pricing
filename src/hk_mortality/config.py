"""Project configuration and source metadata.

All paths are derived from the location of this file so that the project can be
run from any working directory.
"""

from __future__ import annotations

from pathlib import Path

# --------------------------------------------------------------------------- #
# File locations (relative to the project root, which is two levels up)
# --------------------------------------------------------------------------- #
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"

RAW_WORKBOOK = RAW_DIR / "hk_life_tables_2016_2046.xlsx"
TIDY_CSV = PROCESSED_DIR / "hk_life_tables_tidy.csv"
PROVENANCE_JSON = RAW_DIR / "provenance.json"

# --------------------------------------------------------------------------- #
# Official source metadata (recorded in the data-provenance file)
# --------------------------------------------------------------------------- #
SOURCE_TITLE = "Hong Kong Life Tables 2016-2046"
PUBLISHER = "Census and Statistics Department, Hong Kong SAR Government"
SOURCE_WORKBOOK_URL = (
    "https://www.censtatd.gov.hk/en/data/stat_report/product/"
    "B1120016/att/B1120016092023XXXXB01.xlsx"
)
SOURCE_PDF_URL = (
    "https://www.censtatd.gov.hk/en/data/stat_report/product/"
    "B1120016/att/B1120016092023XXXXB01.pdf"
)

# --------------------------------------------------------------------------- #
# Sheet identity -> (reference_year, sex)
#
# These keys are the *observed* sheet titles in the workbook, matched against
# the index sheet (which maps year -> male/female table number).  We never
# guess the sheet identity.
# --------------------------------------------------------------------------- #
SHEET_MAP: dict[str, tuple[int, str]] = {
    "表 2 男性 Table 2 Male (2016)": (2016, "male"),
    "表 3 女性 Table 3 Female (2016)": (2016, "female"),
    "表 12 男性 Table 12 Male (2021)": (2021, "male"),
    "表 13 女性 Table 13 Female (2021)": (2021, "female"),
}

# Tidy output columns.
TIDY_COLUMNS: list[str] = ["reference_year", "sex", "age", "qx", "lx"]

# Mortality cases for the table-year comparison (one publication, two years).
MORTALITY_CASES: tuple[tuple[int, str], ...] = (
    (2016, "male"),
    (2016, "female"),
    (2021, "male"),
    (2021, "female"),
)

# The radix (starting number of survivors) used by all official life tables.
RADIX = 1_000_000
