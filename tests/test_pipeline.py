"""Tests for the mortality data pipeline.

These tests run against the committed source workbook (which is checksum
verified) rather than downloading anything from the network.
"""

from __future__ import annotations

import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import pandas as pd  # noqa: E402
import pytest  # noqa: E402

from hk_mortality import config  # noqa: E402
from hk_mortality.extract import extract_tidy  # noqa: E402
from hk_mortality.validate import validate  # noqa: E402


@pytest.fixture(scope="module")
def tidy() -> pd.DataFrame:
    return extract_tidy()


def test_workbook_exists():
    assert config.RAW_WORKBOOK.exists(), "raw workbook missing"


def test_tidy_columns(tidy):
    assert list(tidy.columns) == config.TIDY_COLUMNS


def test_four_tables_present(tidy):
    keys = tidy.groupby(["reference_year", "sex"]).size()
    assert set(keys.index) == {(2016, "male"), (2016, "female"), (2021, "male"), (2021, "female")}


def test_no_duplicate_keys(tidy):
    dup = tidy.duplicated(subset=["reference_year", "sex", "age"]).sum()
    assert dup == 0


def test_complete_ages(tidy):
    for (year, sex), group in tidy.groupby(["reference_year", "sex"]):
        assert sorted(group["age"].tolist()) == list(range(100)), (year, sex)


def test_numeric_types(tidy):
    assert pd.api.types.is_integer_dtype(tidy["age"])
    assert pd.api.types.is_numeric_dtype(tidy["qx"])
    assert pd.api.types.is_numeric_dtype(tidy["lx"])


def test_qx_is_probability(tidy):
    assert (tidy["qx"] >= 0).all()
    assert (tidy["qx"] <= 1).all()
    # qx values are clearly probabilities, not percentages: all are < 1.
    assert (tidy["qx"] < 1).all()


def test_radix_is_one_million(tidy):
    for (year, sex), group in tidy.groupby(["reference_year", "sex"]):
        radix = int(group.loc[group["age"] == 0, "lx"].iloc[0])
        assert radix == config.RADIX, (year, sex)


def test_validation_report_clean(tidy):
    report = validate(tidy)
    assert not report.errors, report.errors
