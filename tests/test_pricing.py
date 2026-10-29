"""Tests for the term-life pricing engine."""

from __future__ import annotations

import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import math  # noqa: E402

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import pytest  # noqa: E402

from hk_mortality.pricing import (  # noqa: E402
    BASE_INPUTS,
    PricingInputs,
    load_tidy,
    price_case,
    price_net_single_premium,
    qx_by_age,
)


@pytest.fixture(scope="module")
def tidy() -> pd.DataFrame:
    return load_tidy()


def _premium(tidy, year, sex):
    return price_case(tidy, year, sex, BASE_INPUTS)[0]


def test_audit_shape(tidy):
    premium, audit = price_case(tidy, 2016, "male", BASE_INPUTS)
    assert len(audit) == BASE_INPUTS.term
    assert list(audit.columns) == [
        "policy_year",
        "attained_age",
        "qx",
        "survival_to_start",
        "death_probability",
        "discount_factor",
        "expected_claim",
        "pv_claim",
    ]


def test_attained_ages_40_to_59(tidy):
    _, audit = price_case(tidy, 2016, "male", BASE_INPUTS)
    assert audit["attained_age"].tolist() == list(range(40, 60))


def test_premium_equals_sum_of_pv_claim(tidy):
    premium, audit = price_case(tidy, 2021, "female", BASE_INPUTS)
    assert premium == pytest.approx(audit["pv_claim"].sum(), rel=1e-12)


def test_discount_factor(tidy):
    _, audit = price_case(tidy, 2016, "male", BASE_INPUTS)
    r = BASE_INPUTS.interest_rate
    expected = [(1 + r) ** (-k) for k in audit["policy_year"]]
    assert audit["discount_factor"].tolist() == pytest.approx(expected, rel=1e-12)


def test_survival_updates(tidy):
    _, audit = price_case(tidy, 2016, "male", BASE_INPUTS)
    # survival_to_start in year 1 is 1.0.
    assert audit["survival_to_start"].iloc[0] == 1.0
    # Each subsequent survival equals previous * (1 - qx_previous).
    prev = 1.0
    for q_age in audit["qx"]:
        assert audit.loc[audit["qx"] == q_age] is not None  # sanity
    for idx in range(1, len(audit)):
        expected = prev * (1 - audit["qx"].iloc[idx - 1])
        assert audit["survival_to_start"].iloc[idx] == pytest.approx(
            expected, rel=1e-12
        )
        prev = expected


def test_premium_positive_and_bounded(tidy):
    for year, sex in [(2016, "male"), (2016, "female"), (2021, "male"), (2021, "female")]:
        premium = _premium(tidy, year, sex)
        assert 0 < premium < BASE_INPUTS.benefit


def test_alignment_by_age_label_not_position(tidy):
    # Reorder rows of the schedule; the premium must be unchanged because
    # qx is looked up by age label, not row position.
    qx = qx_by_age(tidy, 2016, "male")
    shuffled = dict(sorted(qx.items(), key=lambda kv: -kv[0]))
    premium_ordered = price_net_single_premium(qx, BASE_INPUTS)[0]
    premium_shuffled = price_net_single_premium(shuffled, BASE_INPUTS)[0]
    assert premium_ordered == pytest.approx(premium_shuffled, rel=1e-12)


def test_missing_age_raises(tidy):
    qx = qx_by_age(tidy, 2016, "male")
    del qx[45]  # remove a required age (40..59)
    with pytest.raises(ValueError, match="missing qx for required ages"):
        price_net_single_premium(qx, BASE_INPUTS)


def test_invalid_inputs_raise():
    with pytest.raises(ValueError, match="issue_age"):
        price_net_single_premium({40: 0.01}, PricingInputs(issue_age=-1))
    with pytest.raises(ValueError, match="term"):
        price_net_single_premium({40: 0.01}, PricingInputs(term=0))
    with pytest.raises(ValueError, match="benefit"):
        price_net_single_premium({40: 0.01}, PricingInputs(benefit=0))
    with pytest.raises(ValueError, match="interest_rate"):
        price_net_single_premium({40: 0.01}, PricingInputs(interest_rate=-1.0))


def test_missing_schedule_raises(tidy):
    with pytest.raises(ValueError, match="no mortality data"):
        price_case(tidy, 1999, "male", BASE_INPUTS)


# --------------------------------------------------------------------------- #
# Stage 3: validation tests requested by the user
# --------------------------------------------------------------------------- #

# Deterministic, clearly-labelled test-only schedules used for the pure
# algebraic tests below.  These are NOT real mortality data and must never be
# exported as empirical results.
SYNTHETIC_QX = {age: 0.01 for age in range(40, 60)}
SYNTHETIC_INPUTS = PricingInputs(issue_age=40, term=20, benefit=1_000_000.0)


def test_1_rejects_bad_qx_duplicates_and_missing(tidy):
    # (a) qx outside [0, 1]
    bad = dict(SYNTHETIC_QX)
    bad[50] = 1.05
    with pytest.raises(ValueError, match="outside \\[0, 1\\]"):
        price_net_single_premium(bad, SYNTHETIC_INPUTS)
    bad2 = dict(SYNTHETIC_QX)
    bad2[50] = -0.01
    with pytest.raises(ValueError, match="outside \\[0, 1\\]"):
        price_net_single_premium(bad2, SYNTHETIC_INPUTS)

    # (b) duplicate ages in the schedule
    dup = pd.DataFrame(
        [
            {"reference_year": 2016, "sex": "male", "age": 45, "qx": 0.01, "lx": 1},
            {"reference_year": 2016, "sex": "male", "age": 45, "qx": 0.02, "lx": 1},
        ]
        + [
            {"reference_year": 2016, "sex": "male", "age": a, "qx": 0.01, "lx": 1}
            for a in range(40, 60)
            if a != 45
        ]
    )
    with pytest.raises(ValueError, match="duplicate age"):
        qx_by_age(dup, 2016, "male")

    # (c) missing required ages
    missing = dict(SYNTHETIC_QX)
    del missing[55]
    with pytest.raises(ValueError, match="missing qx for required ages"):
        price_net_single_premium(missing, SYNTHETIC_INPUTS)


def test_2_survival_starts_at_1_and_never_increases(tidy):
    for year, sex in [(2016, "male"), (2016, "female"), (2021, "male"), (2021, "female")]:
        _, audit = price_case(tidy, year, sex, BASE_INPUTS)
        surv = audit["survival_to_start"].to_numpy()
        assert surv[0] == 1.0
        assert np.all(np.diff(surv) <= 0.0), "survival must be non-increasing"


def test_3_total_death_prob_plus_survival_equals_1(tidy):
    for year, sex in [(2016, "male"), (2016, "female"), (2021, "male"), (2021, "female")]:
        _, audit = price_case(tidy, year, sex, BASE_INPUTS)
        total_death_prob = audit["death_probability"].sum()
        survival_to_expiry = audit["survival_to_start"].iloc[-1] * (
            1 - audit["qx"].iloc[-1]
        )
        assert total_death_prob + survival_to_expiry == pytest.approx(1.0, abs=1e-12)


def test_4_one_year_contract_equals_benefit_qx_over_1_plus_i():
    q = 0.02
    i = 0.05
    premium, _ = price_net_single_premium(
        {40: q}, PricingInputs(issue_age=40, term=1, benefit=1_000_000.0, interest_rate=i)
    )
    assert premium == pytest.approx(1_000_000.0 * q / (1 + i), rel=1e-12)


def test_5_zero_interest_premium_equals_benefit_times_death_prob():
    # At zero interest the discount factor is 1 every year, so the premium is
    # benefit * P(death during the term).
    premium, audit = price_net_single_premium(
        SYNTHETIC_QX,
        PricingInputs(issue_age=40, term=20, benefit=1_000_000.0, interest_rate=0.0),
    )
    assert premium == pytest.approx(1_000_000.0 * audit["death_probability"].sum(), rel=1e-12)


def test_6_doubling_benefit_doubles_premium():
    single = price_net_single_premium(SYNTHETIC_QX, SYNTHETIC_INPUTS)[0]
    doubled = price_net_single_premium(
        SYNTHETIC_QX,
        PricingInputs(issue_age=40, term=20, benefit=2_000_000.0),
    )[0]
    assert doubled == pytest.approx(2 * single, rel=1e-12)


def test_7_increasing_interest_reduces_premium():
    premiums = [
        price_net_single_premium(
            SYNTHETIC_QX,
            PricingInputs(issue_age=40, term=20, benefit=1_000_000.0, interest_rate=i),
        )[0]
        for i in (0.0, 0.02, 0.05, 0.10)
    ]
    assert all(
        later < earlier for earlier, later in zip(premiums, premiums[1:])
    ), "higher interest must lower the premium"


def test_8_survival_from_qx_matches_lx_ratios(tidy):
    """Survival derived from qx should match published lx ratios.

    The official lx column is rounded to an integer at each age, so the
    survival curve implied by the published qx differs from lx / lx0 by a
    random walk of rounding errors whose magnitude stays far below the
    printed precision.  We document the measured maximum deviation rather
    than tightening the tolerance arbitrarily.
    """
    from hk_mortality.config import RADIX

    max_dev = 0.0
    for year, sex in [(2016, "male"), (2016, "female"), (2021, "male"), (2021, "female")]:
        qx = qx_by_age(tidy, year, sex)
        lx = dict(zip(tidy[(tidy["reference_year"] == year) & (tidy["sex"] == sex)]["age"],
                      tidy[(tidy["reference_year"] == year) & (tidy["sex"] == sex)]["lx"]))

        ages = sorted(a for a in qx if a in lx)
        lx0 = lx[ages[0]]
        # Survival through age a (i.e. still alive at the START of that age)
        # is cumprod(1 - qx) over all strictly younger ages; this equals the
        # published lx[a] / lx0 ratio.  Aligning by age label avoids any
        # off-by-one in row positions.
        survival = 1.0
        for a in ages:
            ratio = lx[a] / lx0
            max_dev = max(max_dev, abs(survival - ratio))
            survival *= 1.0 - qx[a]

    # Worst measured deviation is ~6e-6 (integer-rounding random walk); 1e-4
    # gives a clear margin over the largest real publication-rounding artefact.
    assert max_dev < 1e-4, f"survival/lx deviation {max_dev:.2e} exceeds 1e-4"
