"""Comparison analyses for the term-life pricing project.

This module holds the *what-if* analyses that sit on top of the pricing engine.
It is kept separate from data download/cleaning and from plotting so that the
pricing arithmetic remains auditable in isolation.

Three analyses are provided:

1. **2016 vs 2021** — for each sex, holding every other assumption constant,
   report the absolute and percentage premium difference attributable to the
   change in the mortality basis.
2. **Interest-rate sensitivity** — price the 2021 basis at 2%, 3% and 4%.
3. **Mortality stress** — price the 2021 basis at 3% with every covered qx
   multiplied by 1.10 (capped at 1), recomputing survival from the stressed
   qx.  This 10% stress is an *arbitrary what-if assumption*, not a forecast,
   a confidence interval, or a regulatory calibration.

Finally, a per-policy-year decomposition of the 2016-vs-2021 premium
difference is provided so that the contribution of each policy year can be
identified; the signed contributions sum exactly to the total difference.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

import numpy as np
import pandas as pd

from .pricing import PricingInputs, price_net_single_premium, qx_by_age

# --------------------------------------------------------------------------- #
# Stress helper
# --------------------------------------------------------------------------- #


def stress_qx(qx: Mapping[int, float], factor: float = 1.10) -> dict[int, float]:
    """Return qx multiplied by `factor`, capped at 1 (a valid probability).

    The 10% stress is an arbitrary what-if assumption, not a forecast.
    Survival is *not* adjusted here; it is recomputed from the stressed qx by
    the pricing engine, exactly as required.
    """
    return {age: min(1.0, factor * float(q)) for age, q in qx.items()}


# --------------------------------------------------------------------------- #
# Analysis 1: reference-year comparison
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class YearComparison:
    sex: str
    premium_2016: float
    premium_2021: float

    @property
    def absolute_diff(self) -> float:
        """premium_2021 - premium_2016 (negative means 2021 basis is cheaper)."""
        return self.premium_2021 - self.premium_2016

    @property
    def pct_diff(self) -> float:
        """Percentage change of 2021 relative to 2016."""
        return 100.0 * self.absolute_diff / self.premium_2016


def compare_years(
    tidy: pd.DataFrame, sex: str, inputs: PricingInputs
) -> YearComparison:
    """Compare the 2016 and 2021 basis for one sex, all else held constant."""
    p16 = price_net_single_premium(qx_by_age(tidy, 2016, sex), inputs)[0]
    p21 = price_net_single_premium(qx_by_age(tidy, 2021, sex), inputs)[0]
    return YearComparison(sex=sex, premium_2016=p16, premium_2021=p21)


# --------------------------------------------------------------------------- #
# Analysis 2: interest-rate sensitivity
# --------------------------------------------------------------------------- #


def interest_sensitivity(
    tidy: pd.DataFrame,
    inputs: PricingInputs,
    rates: tuple[float, ...] = (0.02, 0.03, 0.04),
    cases: tuple[tuple[int, str], ...] | None = None,
) -> pd.DataFrame:
    """Price every (reference_year, sex) case at each interest rate.

    Returns a long DataFrame: reference_year, sex, interest_rate,
    net_single_premium.
    """
    from . import config

    cases = cases if cases is not None else config.MORTALITY_CASES
    rows: list[dict] = []
    for reference_year, sex in cases:
        qx = qx_by_age(tidy, reference_year, sex)
        for rate in rates:
            premium = price_net_single_premium(
                qx, PricingInputs(
                    issue_age=inputs.issue_age,
                    term=inputs.term,
                    benefit=inputs.benefit,
                    interest_rate=rate,
                )
            )[0]
            rows.append(
                {
                    "reference_year": reference_year,
                    "sex": sex,
                    "interest_rate": rate,
                    "net_single_premium": premium,
                }
            )
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- #
# Analysis 3: mortality stress
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class StressComparison:
    reference_year: int
    sex: str
    premium_base: float
    premium_stressed: float

    @property
    def absolute_diff(self) -> float:
        return self.premium_stressed - self.premium_base

    @property
    def pct_diff(self) -> float:
        return 100.0 * self.absolute_diff / self.premium_base


def stress_premium(
    tidy: pd.DataFrame,
    reference_year: int,
    sex: str,
    inputs: PricingInputs,
    factor: float = 1.10,
) -> StressComparison:
    """Price a basis and its 10%-stressed variant, holding interest fixed.

    The stressed survival is recomputed from the stressed qx by the pricing
    engine (survival_to_start is multiplied by (1 - qx_stressed) each year).
    """
    qx = qx_by_age(tidy, reference_year, sex)
    base = price_net_single_premium(qx, inputs)[0]
    stressed = price_net_single_premium(stress_qx(qx, factor), inputs)[0]
    return StressComparison(
        reference_year=reference_year,
        sex=sex,
        premium_base=base,
        premium_stressed=stressed,
    )


# --------------------------------------------------------------------------- #
# Contribution decomposition (distinctive explanation)
# --------------------------------------------------------------------------- #


def pv_contribution_diff(
    tidy: pd.DataFrame, sex: str, inputs: PricingInputs
) -> pd.DataFrame:
    """Per-policy-year present-value contributions for 2016 vs 2021.

    Returns a DataFrame with policy_year, attained_age, pv_claim_2016,
    pv_claim_2021 and difference = pv_claim_2016 - pv_claim_2021.  The
    differences sum exactly to the total premium difference
    (premium_2016 - premium_2021) because both premiums are sums of the
    per-year present values computed from the *same* survival recursion.
    """
    _, audit16 = price_net_single_premium(qx_by_age(tidy, 2016, sex), inputs)
    _, audit21 = price_net_single_premium(qx_by_age(tidy, 2021, sex), inputs)

    out = pd.DataFrame(
        {
            "policy_year": audit16["policy_year"],
            "attained_age": audit16["attained_age"],
            "pv_claim_2016": audit16["pv_claim"],
            "pv_claim_2021": audit21["pv_claim"],
        }
    )
    out["difference"] = out["pv_claim_2016"] - out["pv_claim_2021"]
    return out


def total_premium_difference(
    tidy: pd.DataFrame, sex: str, inputs: PricingInputs
) -> float:
    """Total premium difference (premium_2016 - premium_2021)."""
    return compare_years(tidy, sex, inputs).premium_2016 - compare_years(
        tidy, sex, inputs
    ).premium_2021
