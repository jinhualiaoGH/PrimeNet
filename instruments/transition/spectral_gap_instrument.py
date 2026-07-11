"""
PrimeNet Spectral Gap Instrument

Computes eigenvalue-based spectral diagnostics from a transition matrix.

Metrics:
    lambda_1_abs
    lambda_2_abs
    spectral_gap
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from core.instrument import PrimeNetInstrument


class SpectralGapInstrument(PrimeNetInstrument):
    instrument_id = "INST-SPECTRAL-GAP"
    instrument_name = "Spectral Gap Instrument"
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
        self.eigenvalues: np.ndarray | None = None
        self.summary: dict[str, Any] = {}

    def prepare(self) -> None:
        self.log("Preparing spectral gap instrument.")

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

        eigenvalues = np.linalg.eigvals(transition)
        abs_eigs = np.sort(np.abs(eigenvalues))[::-1]

        self.eigenvalues = eigenvalues

        lambda_1 = float(abs_eigs[0])
        lambda_2 = float(abs_eigs[1]) if len(abs_eigs) > 1 else 0.0
        spectral_gap = lambda_1 - lambda_2

        self.metrics["matrix_size"] = int(transition.shape[0])
        self.metrics["lambda_1_abs"] = lambda_1
        self.metrics["lambda_2_abs"] = lambda_2
        self.metrics["spectral_gap"] = float(spectral_gap)

        self.log("Spectral gap computed.")

    def validate(self) -> None:
        self.log("Validating spectral diagnostics.")

        gap = float(self.metrics["spectral_gap"])

        if gap < -1e-12:
            raise RuntimeError("Spectral gap is negative.")

        self.metrics["spectral_validation_passed"] = True
        self.log("Spectral validation passed.")

    def generate_products(self) -> None:
        self.log("Saving spectral gap products.")

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

        csv_path = product_root / "spectral_eigenvalues.csv"
        eigen_df.to_csv(csv_path, index=False)

        self.products["spectral_eigenvalues_csv"] = str(csv_path)

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
            filename="spectral_gap_summary.json",
            data=self.summary,
        )

        self.products["spectral_gap_summary"] = str(json_path)

        self.log("Spectral gap products saved.")

    def main_report(self) -> None:
        print()
        print("Spectral Gap Instrument completed successfully.")
        print(f"lambda_1_abs  : {self.metrics.get('lambda_1_abs')}")
        print(f"lambda_2_abs  : {self.metrics.get('lambda_2_abs')}")
        print(f"spectral_gap  : {self.metrics.get('spectral_gap')}")


def main() -> None:
    from core.session import PrimeNetSession

    with PrimeNetSession(session_name="Spectral Gap Instrument Test") as session:
        instrument = SpectralGapInstrument(session=session)
        result = instrument.run()

        instrument.main_report()
        print(f"Status: {result.status}")
        print(f"Runtime: {result.runtime_sec:.3f} sec")
        print("Products:")
        for name, path in result.products.items():
            print(f"  {name}: {path}")


if __name__ == "__main__":
    main()