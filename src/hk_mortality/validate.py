"""Data-quality checks for the tidy mortality table.

The checks cover:
  * duplicate keys (reference_year, sex, age)
  * missing ages (each table must contain ages 0..99)
  * numeric types
  * qx bounds (must be a probability in [0, 1], not a percentage)
  * the life-table radix (l0 must equal 1,000,000)
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from . import config


@dataclass
class ValidationReport:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def validate(tidy: pd.DataFrame) -> ValidationReport:
    report = ValidationReport()

    # Column contract.
    if list(tidy.columns) != config.TIDY_COLUMNS:
        report.errors.append(
            f"columns {list(tidy.columns)} != expected {config.TIDY_COLUMNS}"
        )

    # Duplicate keys.
    n_dup = int(tidy.duplicated(subset=["reference_year", "sex", "age"]).sum())
    if n_dup:
        report.errors.append(f"{n_dup} duplicate (reference_year, sex, age) key(s)")

    # Numeric types.
    if not pd.api.types.is_integer_dtype(tidy["age"]):
        report.errors.append("age column is not integer dtype")
    if not pd.api.types.is_numeric_dtype(tidy["qx"]):
        report.errors.append("qx column is not numeric dtype")
    if not pd.api.types.is_numeric_dtype(tidy["lx"]):
        report.errors.append("lx column is not numeric dtype")

    # Missing ages: each (year, sex) must contain exactly ages 0..99.
    for (year, sex), group in tidy.groupby(["reference_year", "sex"]):
        ages = sorted(group["age"].tolist())
        expected = list(range(100))
        if ages != expected:
            missing = sorted(set(expected) - set(ages))
            extra = sorted(set(ages) - set(expected))
            report.errors.append(
                f"{year}/{sex}: missing ages {missing[:10]}"
                + (f", extra {extra[:10]}" if extra else "")
            )

    # qx is a probability in [0, 1].
    if (tidy["qx"] < 0).any():
        report.errors.append("negative qx value(s) present")
    if (tidy["qx"] > 1).any():
        report.errors.append("qx value(s) > 1 (qx must be a probability, not a percentage)")
    qx_max = float(tidy["qx"].max())
    if qx_max > 1:
        report.warnings.append(
            f"max qx = {qx_max:.4f}; qx appears to be a percentage or central rate, "
            "not a probability"
        )

    # Radix.
    for (year, sex), group in tidy.groupby(["reference_year", "sex"]):
        radix = int(group.loc[group["age"] == 0, "lx"].iloc[0])
        if radix != config.RADIX:
            report.warnings.append(
                f"{year}/{sex}: radix l0 = {radix:,} != {config.RADIX:,}"
            )

    return report
