"""
PrimeNet Entropy Rate Instrument

Computes a Markov-chain entropy-rate diagnostic from a transition matrix.

Entropy rate:
    H = - sum_i pi_i sum_j P_ij log2(P_ij)

where:
    P  = row-normalized transition matrix
    pi = stationary-style distribution estimated from row mass
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from core.instrument import PrimeNetInstrument


class EntropyRateInstrument(PrimeNetInstrument):
    instrument_id = "INST-ENTROPY-RATE"
    instrument_name = "Entropy Rate Instrument"
    instrument_category = "transition"
    instrument_version = "1.0.0"

    def __init__(
        self,
        session=None,
        matrix_path: str | Path | None = None,
    ) -> None:
        super().__init__(session=session)

        self.matrix_path = Path(matrix_path) if matrix_path is not None else None
        self.matrix: pd.DataFrame | None = None
        self.transition_matrix: np.ndarray | None = None
        self.state_entropy: pd.DataFrame | None = None
        self.summary: dict[str, Any] = {}

    def prepare(self) -> None:
        self.log("Preparing entropy rate instrument.")

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

    def measure(self) -> None:
        self.log("Loading transition matrix.")

        df = pd.read_csv(self.matrix_path)

        if df.empty:
            raise ValueError("Transition matrix is empty.")

        self.matrix = df

        numeric_cols = df.select_dtypes(include="number").columns.tolist()

        if not numeric_cols:
            raise ValueError("No numeric transition columns found.")

        numeric = df[numeric_cols].to_numpy(dtype=float)

        if numeric.shape[0] != numeric.shape[1]:
            n = min(numeric.shape)
            numeric = numeric[:n, :n]
            numeric_cols = numeric_cols[:n]

        row_mass = numeric.sum(axis=1)
        total_mass = float(row_mass.sum())

        if total_mass <= 0:
            raise ValueError("Total transition mass must be positive.")

        pi = row_mass / total_mass

        row_sums = row_mass.reshape(-1, 1)
        row_sums[row_sums == 0.0] = 1.0

        P = numeric / row_sums
        self.transition_matrix = P

        with np.errstate(divide="ignore", invalid="ignore"):
            logP = np.where(P > 0, np.log2(P), 0.0)

        row_entropy = -np.sum(np.where(P > 0, P * logP, 0.0), axis=1)
        entropy_rate = float(np.sum(pi * row_entropy))

        self.state_entropy = pd.DataFrame(
            {
                "state": numeric_cols,
                "state_mass": row_mass,
                "stationary_weight": pi,
                "conditional_entropy_bits": row_entropy,
                "weighted_entropy_contribution": pi * row_entropy,
            }
        ).sort_values("weighted_entropy_contribution", ascending=False)

        self.metrics["states"] = int(len(numeric_cols))
        self.metrics["total_mass"] = total_mass
        self.metrics["entropy_rate_bits"] = entropy_rate
        self.metrics["max_state_entropy_bits"] = float(row_entropy.max())
        self.metrics["min_state_entropy_bits"] = float(row_entropy.min())
        self.metrics["mean_state_entropy_bits"] = float(row_entropy.mean())

        self.log("Entropy rate computed.")

    def validate(self) -> None:
        self.log("Validating entropy rate diagnostics.")

        entropy_rate = float(self.metrics["entropy_rate_bits"])

        if entropy_rate < -1e-12:
            raise RuntimeError("Entropy rate is negative.")

        self.metrics["entropy_rate_validation_passed"] = True
        self.log("Entropy rate validation passed.")

    def generate_products(self) -> None:
        self.log("Saving entropy rate products.")

        if self.state_entropy is None:
            raise RuntimeError("No state entropy table computed.")

        product_root = self.products_service.product_root(
            category=self.instrument_category,
            observatory_id=self.instrument_id.lower(),
        )

        csv_path = product_root / "entropy_rate_state_table.csv"
        self.state_entropy.to_csv(csv_path, index=False)

        self.products["entropy_rate_state_table_csv"] = str(csv_path)

        self.summary = {
            "instrument_id": self.instrument_id,
            "instrument_name": self.instrument_name,
            "instrument_category": self.instrument_category,
            "instrument_version": self.instrument_version,
            "input_file": str(self.matrix_path),
            "metrics": self.metrics,
            "products": self.products,
        }

        json_path = self.products_service.save_json(
            category=self.instrument_category,
            observatory_id=self.instrument_id.lower(),
            filename="entropy_rate_summary.json",
            data=self.summary,
        )

        self.products["entropy_rate_summary"] = str(json_path)

        self.log("Entropy rate products saved.")

    def main_report(self) -> None:
        print()
        print("Entropy Rate Instrument completed successfully.")
        print(f"states              : {self.metrics.get('states')}")
        print(f"entropy_rate_bits   : {self.metrics.get('entropy_rate_bits')}")
        print(f"max_state_entropy   : {self.metrics.get('max_state_entropy_bits')}")
        print(f"mean_state_entropy  : {self.metrics.get('mean_state_entropy_bits')}")


def main() -> None:
    from core.session import PrimeNetSession

    with PrimeNetSession(session_name="Entropy Rate Instrument Test") as session:
        instrument = EntropyRateInstrument(session=session)
        result = instrument.run()

        instrument.main_report()
        print(f"Status: {result.status}")
        print(f"Runtime: {result.runtime_sec:.3f} sec")
        print("Products:")
        for name, path in result.products.items():
            print(f"  {name}: {path}")


if __name__ == "__main__":
    main()