"""Run the term-life pricing engine across all four mortality cases.

Produces:
  * results/pricing_comparison.csv     - one row per (reference_year, sex)
  * results/cashflow_<year>_<sex>.csv  - the year-by-year audit table

Run from the project root:

    python scripts/run_pricing.py
"""

from __future__ import annotations

import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import pandas as pd  # noqa: E402

from hk_mortality import config  # noqa: E402
from hk_mortality.pricing import (  # noqa: E402
    BASE_INPUTS,
    load_tidy,
    price_case,
)

RESULTS_DIR = config.PROJECT_ROOT / "results"
COMPARISON_CSV = RESULTS_DIR / "pricing_comparison.csv"


def main() -> int:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    tidy = load_tidy()
    inputs = BASE_INPUTS

    comparison: list[dict] = []

    print("=" * 72)
    print("Term-life net single premium (controlled comparison)")
    print(
        f"issue_age={inputs.issue_age} term={inputs.term} "
        f"benefit={inputs.benefit:,.0f} interest_rate={inputs.interest_rate:.2%}"
    )
    print("=" * 72)

    for reference_year, sex in config.MORTALITY_CASES:
        premium, audit = price_case(tidy, reference_year, sex, inputs)

        audit_path = RESULTS_DIR / f"cashflow_{reference_year}_{sex}.csv"
        audit.to_csv(audit_path, index=False)

        comparison.append(
            {
                "reference_year": reference_year,
                "sex": sex,
                "issue_age": inputs.issue_age,
                "term": inputs.term,
                "benefit": inputs.benefit,
                "interest_rate": inputs.interest_rate,
                "net_single_premium": premium,
            }
        )
        print(
            f"  {reference_year} {sex:6s} -> net single premium = "
            f"HKD {premium:,.2f}   (audit: {audit_path.name})"
        )

    comparison_df = pd.DataFrame(comparison)
    comparison_df.to_csv(COMPARISON_CSV, index=False)
    print(f"\nComparison written to: {COMPARISON_CSV}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
