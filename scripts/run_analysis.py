"""Run the comparison analyses and produce charts + CSVs (stage 3).

Usage:
    python scripts/run_analysis.py

Reads the cleaned tidy mortality table, runs the three analyses, and writes:
    results/pricing_comparison_by_year.csv   (2016 vs 2021, per sex)
    results/interest_sensitivity.csv         (2/3/4% for all four cases)
    results/stress_comparison.csv            (2021 @ 3%, +10% qx stress)
    results/mortality_curves.csv/.png
    results/premium_vs_interest.csv/.png
    results/pv_contribution_male.csv/.png
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from hk_mortality import analysis, config, plots  # noqa: E402
from hk_mortality.pricing import BASE_INPUTS, load_tidy  # noqa: E402


def main() -> None:
    out_dir = config.PROJECT_ROOT / "results"
    out_dir.mkdir(parents=True, exist_ok=True)

    tidy = load_tidy()

    # --- Analysis 1: 2016 vs 2021, per sex ---------------------------------
    comparisons = [
        analysis.compare_years(tidy, sex, BASE_INPUTS)
        for sex in ("male", "female")
    ]
    comp_rows = [
        {
            "sex": c.sex,
            "premium_2016": c.premium_2016,
            "premium_2021": c.premium_2021,
            "absolute_diff_2021_minus_2016": c.absolute_diff,
            "pct_diff_2021_vs_2016": c.pct_diff,
        }
        for c in comparisons
    ]
    comp_df = pd.DataFrame(comp_rows)
    comp_path = out_dir / "pricing_comparison_by_year.csv"
    comp_df.to_csv(comp_path, index=False)
    print(f"wrote {comp_path.relative_to(config.PROJECT_ROOT)}")
    print(comp_df.round(4).to_string(index=False))
    print()

    # --- Analysis 2: interest-rate sensitivity ------------------------------
    sens = analysis.interest_sensitivity(
        tidy, BASE_INPUTS, rates=(0.02, 0.03, 0.04)
    )
    sens_path = out_dir / "interest_sensitivity.csv"
    sens.to_csv(sens_path, index=False)
    print(f"wrote {sens_path.relative_to(config.PROJECT_ROOT)}")
    print(sens.round(4).to_string(index=False))
    print()

    # --- Analysis 3: 10% mortality stress (2021 @ 3%) -----------------------
    stress_rows = []
    for reference_year, sex in config.MORTALITY_CASES:
        s = analysis.stress_premium(tidy, reference_year, sex, BASE_INPUTS)
        stress_rows.append(
            {
                "reference_year": reference_year,
                "sex": sex,
                "premium_base": s.premium_base,
                "premium_stressed": s.premium_stressed,
                "absolute_diff": s.absolute_diff,
                "pct_diff": s.pct_diff,
            }
        )
    stress_df = pd.DataFrame(stress_rows)
    stress_path = out_dir / "stress_comparison.csv"
    stress_df.to_csv(stress_path, index=False)
    print(f"wrote {stress_path.relative_to(config.PROJECT_ROOT)}")
    print(stress_df.round(4).to_string(index=False))
    print()

    # --- Charts --------------------------------------------------------------
    png1, csv1 = plots.mortality_curves(tidy)
    print(f"wrote {png1.relative_to(config.PROJECT_ROOT)}")
    print(f"wrote {csv1.relative_to(config.PROJECT_ROOT)}")

    png2, csv2 = plots.premium_vs_interest(sens)
    print(f"wrote {png2.relative_to(config.PROJECT_ROOT)}")
    print(f"wrote {csv2.relative_to(config.PROJECT_ROOT)}")

    contrib = analysis.pv_contribution_diff(tidy, "male", BASE_INPUTS)
    png3, csv3 = plots.pv_contribution(contrib, sex="male")
    print(f"wrote {png3.relative_to(config.PROJECT_ROOT)}")
    print(f"wrote {csv3.relative_to(config.PROJECT_ROOT)}")

    # --- Distinctive explanation: contribution decomposition -----------------
    total_diff = contrib["difference"].sum()
    print()
    print("Distinctive explanation: per-policy-year contribution difference")
    print("(2016 male - 2021 male pv_claim). Sum must equal the total")
    print("premium difference 2016 - 2021.")
    print(f"sum of per-year differences = {total_diff:.4f}")
    print(
        "total premium difference = "
        f"{analysis.total_premium_difference(tidy, 'male', BASE_INPUTS):.4f}"
    )


if __name__ == "__main__":
    main()
