"""
PrimeNet Stationary Distribution Instrument

Computes a simple stationary-style distribution from a transition matrix.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from core.instrument import PrimeNetInstrument


class StationaryDistributionInstrument(PrimeNetInstrument):
    """
    Computes a normalized stationary-style distribution using
    transition matrix column mass.
    """

    instrument_id = "INST-STATIONARY-DISTRIBUTION"
    instrument_name = "Stationary Distribution Instrument"
    instrument_category = "transition"
    instrument_version = "1.0.0"

    def __init__(
        self,
        session=None,
        matrix_path: str |Path | None = None,
    ):
        super().__init__(session=session)

        self.matrix_path = (
            Path(matrix_path)
            if matrix_path is not None
            else None
        )

        self.matrix: pd.DataFrame | None = None
        self.distribution: pd.DataFrame | None = None
        self.summary: dict[str, Any] = {}

    # ---------------------------------------------------------

    def prepare(self):

        self.log("Preparing stationary distribution instrument.")

        if self.matrix_path is None:

            self.matrix_path = (
                Path("C:/Prime_Distribution_Project")
                / "prime_repository_pkg"
                / "results"
                / "PN21_transition_matrix_top100.csv"
            )

        if not self.matrix_path.exists():
            raise FileNotFoundError(self.matrix_path)

        self.log(f"Matrix file: {self.matrix_path}")

    # ---------------------------------------------------------

    def measure(self):

        self.log("Loading transition matrix.")

        df = pd.read_csv(self.matrix_path)

        self.matrix = df

        source_col = df.columns[0]
        state_cols = df.columns[1:].tolist()

        numeric = df[state_cols].apply(pd.to_numeric, errors="coerce").fillna(0.0)

        column_mass = numeric.sum(axis=0)

        total_mass = float(column_mass.sum())

        probability = column_mass / total_mass

        self.distribution = (
            pd.DataFrame(
                {
                    "state": state_cols,
                    "mass": column_mass.values,
                    "probability": probability.values,
                }
            )
            .sort_values("probability", ascending=False)
            .reset_index(drop=True)
        )

        self.metrics["states"] = len(self.distribution)
        self.metrics["source_column"] = source_col
        self.metrics["total_mass"] = total_mass
        self.metrics["max_probability"] = float(
            self.distribution["probability"].max()
        )
        self.metrics["min_probability"] = float(
            self.distribution["probability"].min()
        )

        self.log("Stationary distribution computed.")
    # ---------------------------------------------------------

    def validate(self):

        self.log("Validating distribution.")

        total_probability = float(
            self.distribution["probability"].sum()
        )

        self.metrics["probability_sum"] = total_probability
        self.metrics["probability_error"] = abs(
            total_probability - 1.0
        )

        if abs(total_probability - 1.0) > 1e-9:
            raise RuntimeError("Probability normalization failed.")

        self.log("Validation passed.")

    # ---------------------------------------------------------

    def generate_products(self):

        self.log("Saving products.")

        product_root = self.products_service.product_root(
            category=self.instrument_category,
            observatory_id=self.instrument_id.lower(),
        )

        csv_path = product_root / "stationary_distribution.csv"

        self.distribution.to_csv(csv_path, index=False)

        self.products["stationary_distribution_csv"] = str(csv_path)

        self.summary = {
            "instrument_id": self.instrument_id,
            "instrument_name": self.instrument_name,
            "instrument_version": self.instrument_version,
            "metrics": self.metrics,
            "products": self.products,
        }

        json_path = self.products_service.save_json(
            category=self.instrument_category,
            observatory_id=self.instrument_id.lower(),
            filename="stationary_distribution_summary.json",
            data=self.summary,
        )

        self.products["stationary_distribution_summary"] = str(json_path)

        self.log("Products saved.")

    # ---------------------------------------------------------


def main():

    from core.session import PrimeNetSession

    with PrimeNetSession(
        session_name="Stationary Distribution Instrument Test"
    ) as session:

        instrument = StationaryDistributionInstrument(
            session=session
        )

        result = instrument.run()

        print()
        print("Stationary Distribution Instrument completed successfully.")
        print(f"Status: {result.status}")
        print(f"Runtime: {result.runtime_sec:.3f} sec")
        print()

        print("Products:")

        for name, path in result.products.items():
            print(f"    {name}: {path}")


if __name__ == "__main__":
    main()