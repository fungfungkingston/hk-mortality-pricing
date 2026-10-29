"""Term-life net single premium pricing engine.

This module prices a single, fixed term-life contract using a mortality
schedule read from the tidy mortality table produced by the data pipeline.

The contract is deliberately simple (no lapses, expenses, taxes, profit or
capital loading) and the premium is a **net single premium** — the present
value of expected death claims only.  It is *not* a commercial quote.

Actuarial convention used here: the death benefit is paid at the end of the
policy year in which death occurs, and the first premium is paid at inception.

The pricing is kept fully separate from data download and plotting so that the
calculation can be audited in isolation.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

import pandas as pd

from . import config

# --------------------------------------------------------------------------- #
# Inputs
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class PricingInputs:
    """Fixed assumptions for a single term-life pricing run."""

    issue_age: int = 40
    term: int = 20
    benefit: float = 1_000_000.0
    interest_rate: float = 0.03

    @property
    def required_ages(self) -> range:
        """Ages whose qx values drive policy years 1..term.

        A term-year policy issued at exact age `issue_age` needs qx for
        attained ages `issue_age` .. `issue_age + term - 1`.
        """
        return range(self.issue_age, self.issue_age + self.term)


BASE_INPUTS = PricingInputs()

# --------------------------------------------------------------------------- #
# Data loading / alignment
# --------------------------------------------------------------------------- #


def load_tidy(path: Path | str | None = None) -> pd.DataFrame:
    """Load the tidy mortality table (reference_year, sex, age, qx, lx)."""
    path = Path(path) if path else config.TIDY_CSV
    if not path.exists():
        raise FileNotFoundError(
            f"tidy mortality table not found: {path}. "
            "Run `python scripts/run_pipeline.py` first."
        )
    return pd.read_csv(path)


def qx_by_age(
    tidy: pd.DataFrame, reference_year: int, sex: str
) -> dict[int, float]:
    """Return an age -> qx lookup for one mortality schedule.

    Values are aligned by the *age label*, never by row position, so a
    reordered or filtered input still resolves the correct qx.
    """
    subset = tidy[(tidy["reference_year"] == reference_year) & (tidy["sex"] == sex)]
    if subset.empty:
        raise ValueError(
            f"no mortality data for reference_year={reference_year}, sex={sex!r}"
        )
    if subset["age"].duplicated().any():
        dup_ages = sorted({int(a) for a in subset.loc[subset["age"].duplicated(), "age"]})
        raise ValueError(
            f"duplicate age(s) in mortality schedule for "
            f"reference_year={reference_year}, sex={sex!r}: {dup_ages}"
        )
    return dict(zip(subset["age"], subset["qx"]))


# --------------------------------------------------------------------------- #
# Validation
# --------------------------------------------------------------------------- #


def _validate_inputs(inputs: PricingInputs) -> None:
    if not isinstance(inputs.issue_age, int) or inputs.issue_age < 0:
        raise ValueError(
            f"issue_age must be a non-negative integer, got {inputs.issue_age!r}"
        )
    if not isinstance(inputs.term, int) or inputs.term <= 0:
        raise ValueError(f"term must be a positive integer, got {inputs.term!r}")
    if not isinstance(inputs.benefit, (int, float)) or inputs.benefit <= 0:
        raise ValueError(f"benefit must be a positive number, got {inputs.benefit!r}")
    if not isinstance(inputs.interest_rate, (int, float)) or inputs.interest_rate <= -1:
        raise ValueError(
            f"interest_rate must be greater than -1, got {inputs.interest_rate!r}"
        )


def _validate_schedule(
    qx: Mapping[int, float], inputs: PricingInputs
) -> None:
    missing = [age for age in inputs.required_ages if age not in qx]
    if missing:
        raise ValueError(
            f"mortality schedule is missing qx for required ages "
            f"{missing}; the table must cover ages "
            f"{inputs.required_ages.start}..{inputs.required_ages.stop - 1}"
        )
    bad = {age: value for age, value in qx.items() if not (0.0 <= value <= 1.0)}
    if bad:
        raise ValueError(
            f"qx values outside [0, 1] (not a probability): {bad}"
        )


# --------------------------------------------------------------------------- #
# Pricing
# --------------------------------------------------------------------------- #


def price_net_single_premium(
    qx: Mapping[int, float], inputs: PricingInputs
) -> tuple[float, pd.DataFrame]:
    """Price the net single premium and return (premium, audit_table).

    The audit table has one row per policy year with columns:

        policy_year, attained_age, qx, survival_to_start,
        death_probability, discount_factor, expected_claim, pv_claim.

    Full floating-point precision is preserved throughout; no rounding is
    applied to intermediate values.
    """
    _validate_inputs(inputs)
    _validate_schedule(qx, inputs)

    i = inputs.interest_rate
    rows: list[dict] = []
    survival_to_start = 1.0
    premium = 0.0

    for k in range(inputs.term):
        attained_age = inputs.issue_age + k
        q_age = float(qx[attained_age])

        death_probability = survival_to_start * q_age
        discount_factor = (1.0 + i) ** (-(k + 1))
        expected_claim = inputs.benefit * death_probability
        pv_claim = expected_claim * discount_factor

        rows.append(
            {
                "policy_year": k + 1,
                "attained_age": attained_age,
                "qx": q_age,
                "survival_to_start": survival_to_start,
                "death_probability": death_probability,
                "discount_factor": discount_factor,
                "expected_claim": expected_claim,
                "pv_claim": pv_claim,
            }
        )

        premium += pv_claim
        survival_to_start *= 1.0 - q_age

    audit = pd.DataFrame(
        rows,
        columns=[
            "policy_year",
            "attained_age",
            "qx",
            "survival_to_start",
            "death_probability",
            "discount_factor",
            "expected_claim",
            "pv_claim",
        ],
    )
    return premium, audit


def price_case(
    tidy: pd.DataFrame, reference_year: int, sex: str, inputs: PricingInputs
) -> tuple[float, pd.DataFrame]:
    """Convenience wrapper: select a schedule from the tidy table and price it."""
    qx = qx_by_age(tidy, reference_year, sex)
    return price_net_single_premium(qx, inputs)
