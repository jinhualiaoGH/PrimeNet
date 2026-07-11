"""
PrimeNet Mixing Time Instrument

Estimates Markov-chain mixing diagnostics from a transition matrix.

This instrument:
    1. loads a transition matrix
    2. row-normalizes it
    3. computes eigenvalue magnitudes
    4. estimates mixing time from the spectral gap
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from core.instrument import PrimeNetInstrument


class MixingTimeInstrument(PrimeNetInstrument):
    """
    Mixing-time diagnostic instrument for transition matrices.
    """

    instrument_id = "INST-MIXING-TIME"
    instrument_name = "Mixing Time Instrument"
    instrument_category = "transition"
    instrument_version = "1.0.0"

    def __init__(
        self,
        session=None,
        matrix_path: str | Path | None = None,
        epsilon: float = 0.01,
    ) -> None:
        super().__init__(session=session)

        self.matrix_path = Path(matrix_path) if matrix_path is not None else None
        self.epsilon = float(epsilon)

        self.matrix: pd.DataFrame | None = None
        self.transition_matrix: np.ndarray | None = None
        self.eigenvalues: np.ndarray | None = None
        self.summary: dict[str, Any] = {}

    def prepare(self) -> None:
        self.log("Preparing mixing time instrument.")

        if self.matrix_path is None:
            self.matrix_path = (
                Path("C:/Prime_Distribution_Project")
                / "prime_repository_pkg"
                / "results"
                / "PN21_transition_matrix_top100.csv"
            )

        if not self.matrix_path.exists():
            raise FileNotFoundError(self.matrix_path)

        if self.epsilon <= 0 or self.epsilon >= 1:
            raise ValueError("epsilon must be between 0 and 1.")

        self.log(f"Matrix file: {self.matrix_path}")
        self.log(f"Epsilon: {self.epsilon}")

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

        row_sums = numeric.sum(axis=1, keepdims=True)
        row_sums[row_sums == 0.0] = 1.0

        transition = numeric / row_sums
        self.transition_matrix = transition

        eigenvalues = np.linalg.eigvals(transition)
        self.eigenvalues = eigenvalues

        abs_eigs = np.sort(np.abs(eigenvalues))[::-1]

        lambda_1 = float(abs_eigs[0])
        lambda_2 = float(abs_eigs[1]) if len(abs_eigs) > 1 else 0.0
        spectral_gap = lambda_1 - lambda_2

        if spectral_gap <= 0:
            mixing_time_inverse_gap = float("inf")
            mixing_time_log_bound = float("inf")
        else:
            mixing_time_inverse_gap = 1.0 / spectral_gap
            mixing_time_log_bound = np.log(1.0 / self.epsilon) / spectral_gap

        self.metrics["matrix_size"] = int(transition.shape[0])
        self.metrics["epsilon"] = float(self.epsilon)
        self.metrics["lambda_1_abs"] = lambda_1
        self.metrics["lambda_2_abs"] = lambda_2
        self.metrics["spectral_gap"] = float(spectral_gap)
        self.metrics["mixing_time_inverse_gap"] = float(mixing_time_inverse_gap)
        self.metrics["mixing_time_log_bound"] = float(mixing_time_log_bound)

        self.log("Mixing time diagnostics computed.")

    def validate(self) -> None:
        self.log("Validating mixing time diagnostics.")

        gap = float(self.metrics["spectral_gap"])

        if gap < -1e-12:
            raise RuntimeError("Spectral gap is negative.")

        if self.metrics["lambda_1_abs"] > 1.000001:
            raise RuntimeError("Dominant eigenvalue magnitude exceeds 1.")

        self.metrics["mixing_time_validation_passed"] = True
        self.log("Mixing time validation passed.")

    def generate_products(self) -> None:
        self.log("Saving mixing time products.")

        if self.eigenvalues is None:
            raise RuntimeError("No eigenvalues computed.")

        eigen_df = pd.DataFrame(
            {
                "real": np.real(self.eigenvalues),
                "imag": np.imag(self.eigenvalues),
                "abs": np.abs(self.eigenvalues),
            }
        ).sort_values("abs", ascending=False)

        product_root = self.products_service.product_root(
            category=self.instrument_category,
            observatory_id=self.instrument_id.lower(),
        )

        eigen_csv = product_root / "mixing_time_eigenvalues.csv"
        eigen_df.to_csv(eigen_csv, index=False)

        self.products["mixing_time_eigenvalues_csv"] = str(eigen_csv)

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
            filename="mixing_time_summary.json",
            data=self.summary,
        )

        self.products["mixing_time_summary"] = str(json_path)

        self.log("Mixing time products saved.")

    def main_report(self) -> None:
        print()
        print("Mixing Time Instrument completed successfully.")
        print(f"lambda_1_abs              : {self.metrics.get('lambda_1_abs')}")
        print(f"lambda_2_abs              : {self.metrics.get('lambda_2_abs')}")
        print(f"spectral_gap              : {self.metrics.get('spectral_gap')}")
        print(
            f"mixing_time_inverse_gap   : "
            f"{self.metrics.get('mixing_time_inverse_gap')}"
        )
        print(
            f"mixing_time_log_bound     : "
            f"{self.metrics.get('mixing_time_log_bound')}"
        )


def main() -> None:
    from core.session import PrimeNetSession

    with PrimeNetSession(session_name="Mixing Time Instrument Test") as session:
        instrument = MixingTimeInstrument(session=session)
        result = instrument.run()

        instrument.main_report()
        print(f"Status: {result.status}")
        print(f"Runtime: {result.runtime_sec:.3f} sec")
        print("Products:")
        for name, path in result.products.items():
            print(f"  {name}: {path}")


if __name__ == "__main__":
    main()