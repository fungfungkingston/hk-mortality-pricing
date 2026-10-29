"""Matplotlib charts for the comparison analysis.

Each chart is written as a PNG together with the CSV data that underlies it,
so the figure can be reproduced from the CSV alone.  Plotting is kept separate
from pricing and downloading.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # headless backend; must be set before importing pyplot
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from . import config  # noqa: E402

# One clearly identified sex used for the per-policy-year contribution chart.
CONTRIBUTION_SEX = "male"

# Palette for the four mortality cases (one publication, two years, two sexes).
SERIES_STYLE = {
    (2016, "male"): dict(color="#1f77b4", linestyle="-", label="2016 male"),
    (2016, "female"): dict(color="#ff7f0e", linestyle="-", label="2016 female"),
    (2021, "male"): dict(color="#1f77b4", linestyle="--", label="2021 male"),
    (2021, "female"): dict(color="#ff7f0e", linestyle="--", label="2021 female"),
}


def _save(fig, png_path: Path) -> None:
    png_path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(png_path, dpi=150)
    plt.close(fig)


# --------------------------------------------------------------------------- #
# Chart 1: mortality by age, sex and reference year
# --------------------------------------------------------------------------- #


def mortality_curves(tidy: pd.DataFrame) -> tuple[Path, Path]:
    """Plot qx against age for the four schedules; save PNG + underlying CSV."""
    out_dir = config.PROJECT_ROOT / "results"

    pivoted = tidy.pivot_table(
        index="age",
        columns=["reference_year", "sex"],
        values="qx",
    ).sort_index()
    # Flatten the (year, sex) MultiIndex columns into readable names.
    pivoted.columns = [
        f"qx_{year}_{sex}" for year, sex in pivoted.columns
    ]
    csv_path = out_dir / "mortality_curves.csv"
    pivoted.reset_index().to_csv(csv_path, index=False)

    fig, ax = plt.subplots(figsize=(8, 5))
    for (year, sex), style in SERIES_STYLE.items():
        series = tidy[(tidy["reference_year"] == year) & (tidy["sex"] == sex)]
        series = series.sort_values("age")
        ax.plot(series["age"], series["qx"], **style)

    ax.set_yscale("log")
    ax.set_xlabel("Age")
    ax.set_ylabel("qx (log scale)")
    ax.set_title("Hong Kong life-table mortality by age, sex and reference year")
    ax.legend()
    ax.grid(True, which="both", alpha=0.3)

    png_path = out_dir / "mortality_curves.png"
    _save(fig, png_path)
    return png_path, csv_path


# --------------------------------------------------------------------------- #
# Chart 2: net single premium versus interest rate
# --------------------------------------------------------------------------- #


def premium_vs_interest(sensitivity: pd.DataFrame) -> tuple[Path, Path]:
    """Plot net single premium against interest rate for all four cases."""
    out_dir = config.PROJECT_ROOT / "results"
    csv_path = out_dir / "interest_sensitivity.csv"
    sensitivity.to_csv(csv_path, index=False)

    fig, ax = plt.subplots(figsize=(8, 5))
    for (year, sex), style in SERIES_STYLE.items():
        sub = sensitivity[
            (sensitivity["reference_year"] == year)
            & (sensitivity["sex"] == sex)
        ].sort_values("interest_rate")
        ax.plot(
            sub["interest_rate"],
            sub["net_single_premium"],
            marker="o",
            **style,
        )

    ax.set_xlabel("Constant annual effective discount rate")
    ax.set_ylabel("Net single premium (HKD)")
    ax.set_title("Net single premium versus interest rate (issue age 40, term 20)")
    ax.legend()
    ax.grid(True, alpha=0.3)
    ax.xaxis.set_major_formatter(lambda x, _: f"{x:.0%}")

    png_path = out_dir / "premium_vs_interest.png"
    _save(fig, png_path)
    return png_path, csv_path


# --------------------------------------------------------------------------- #
# Chart 3: per-policy-year PV contributions (2016 vs 2021, one sex)
# --------------------------------------------------------------------------- #


def pv_contribution(contribution: pd.DataFrame, sex: str = CONTRIBUTION_SEX) -> tuple[Path, Path]:
    """Plot per-policy-year present values for 2016 vs 2021 (one sex)."""
    out_dir = config.PROJECT_ROOT / "results"
    csv_path = out_dir / f"pv_contribution_{sex}.csv"
    contribution.to_csv(csv_path, index=False)

    fig, ax = plt.subplots(figsize=(9, 5))
    x = contribution["policy_year"]
    ax.plot(x, contribution["pv_claim_2016"], marker="o", label="2016")
    ax.plot(x, contribution["pv_claim_2021"], marker="s", label="2021")
    ax.fill_between(
        x,
        contribution["pv_claim_2016"],
        contribution["pv_claim_2021"],
        alpha=0.15,
        color="grey",
    )

    ax.set_xlabel("Policy year")
    ax.set_ylabel("Present value of expected claim (HKD)")
    ax.set_title(
        f"Policy-year present-value contributions, {sex} "
        "(2016 vs 2021, issue age 40, term 20, 3%)"
    )
    ax.legend()
    ax.grid(True, alpha=0.3)
    ax.set_xticks(x)

    png_path = out_dir / f"pv_contribution_{sex}.png"
    _save(fig, png_path)
    return png_path, csv_path
