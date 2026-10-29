"""Tests for the comparison analysis module (stage 3)."""

from __future__ import annotations

import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import pandas as pd  # noqa: E402
import pytest  # noqa: E402

from hk_mortality.analysis import (  # noqa: E402
    compare_years,
    interest_sensitivity,
    pv_contribution_diff,
    stress_premium,
    stress_qx,
    total_premium_difference,
)
from hk_mortality.pricing import BASE_INPUTS, load_tidy, price_net_single_premium  # noqa: E402


@pytest.fixture(scope="module")
def tidy() -> pd.DataFrame:
    return load_tidy()


def test_stress_qx_caps_at_one():
    qx = {40: 0.95, 41: 0.10}
    out = stress_qx(qx, factor=1.10)
    assert out[40] == 1.0  # 1.10 * 0.95 = 1.045 -> capped
    assert out[41] == pytest.approx(0.11)


def test_stress_recomputes_survival(tidy):
    # The stressed premium must equal a direct pricing run on the stressed
    # schedule, which proves survival was recomputed from stressed qx rather
    # than reused from the base schedule.
    from hk_mortality.analysis import stress_qx as _sq
    from hk_mortality.pricing import qx_by_age

    qx = qx_by_age(tidy, 2021, "male")
    direct = price_net_single_premium(_sq(qx), BASE_INPUTS)[0]
    stressed = stress_premium(tidy, 2021, "male", BASE_INPUTS)
    assert stressed.premium_stressed == pytest.approx(direct, rel=1e-12)
    # A genuine 10% stress should raise the premium (benefits are positive).
    assert stressed.premium_stressed > stressed.premium_base


def test_contribution_difference_sums_to_total(tidy):
    for sex in ("male", "female"):
        contrib = pv_contribution_diff(tidy, sex, BASE_INPUTS)
        total = total_premium_difference(tidy, sex, BASE_INPUTS)
        assert contrib["difference"].sum() == pytest.approx(total, rel=1e-12)


def test_compare_years_returns_consistent_signs(tidy):
    for sex in ("male", "female"):
        c = compare_years(tidy, sex, BASE_INPUTS)
        assert c.absolute_diff == pytest.approx(
            c.premium_2021 - c.premium_2016, rel=1e-12
        )
        assert c.pct_diff == pytest.approx(
            100.0 * c.absolute_diff / c.premium_2016, rel=1e-12
        )


def test_interest_sensitivity_monotonic(tidy):
    sens = interest_sensitivity(tidy, BASE_INPUTS, rates=(0.02, 0.03, 0.04))
    for (year, sex), grp in sens.groupby(["reference_year", "sex"]):
        premiums = grp.sort_values("interest_rate")["net_single_premium"].tolist()
        assert all(
            later < earlier for earlier, later in zip(premiums, premiums[1:])
        ), f"non-monotonic in interest for {year} {sex}"


def test_interest_sensitivity_covers_all_cases(tidy):
    sens = interest_sensitivity(tidy, BASE_INPUTS, rates=(0.02, 0.03, 0.04))
    assert set(map(tuple, sens[["reference_year", "sex"]].drop_duplicates().values.tolist())) == {
        (2016, "male"), (2016, "female"), (2021, "male"), (2021, "female")
    }
