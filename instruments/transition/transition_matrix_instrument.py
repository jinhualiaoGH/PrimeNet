"""
PrimeNet Transition Matrix Instrument

Reusable measurement instrument for transition-matrix data.

This instrument loads a transition matrix, validates it, and computes
standard matrix-level scientific metrics.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from core.instrument import PrimeNetInstrument


class TransitionMatrixInstrument(PrimeNetInstrument):
    """
    Instrument for measuring transition matrix structure.
    """

    instrument_id = "INST-TRANSITION-MATRIX"
    instrument_name = "Transition Matrix Instrument"
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
        self.numeric_columns: list[str] = []
        self.validation_summary: dict[str, Any] = {}
        self.summary: dict[str, Any] = {}

    def prepare(self) -> None:
        self.log("Preparing transition matrix instrument.")

        if self.matrix_path is None:
            self.matrix_path = (
                Path("C:/Prime_Distribution_Project")
                / "prime_repository_pkg"
                / "results"
                / "PN21_transition_matrix_top100.csv"
            )

        self.matrix_path = Path(self.matrix_path)

        self.log(f"Transition matrix path: {self.matrix_path}")

        if not self.matrix_path.exists():
            raise FileNotFoundError(
                f"Transition matrix file not found: {self.matrix_path}"
            )

    def measure(self) -> None:
        self.log("Loading transition matrix.")

        df = pd.read_csv(self.matrix_path)

        if df.empty:
            raise ValueError(f"Transition matrix is empty: {self.matrix_path}")

        self.matrix = df
        self.numeric_columns = df.select_dtypes(include="number").columns.tolist()

        self.metrics["rows"] = int(len(df))
        self.metrics["columns"] = int(len(df.columns))
        self.metrics["numeric_columns"] = int(len(self.numeric_columns))

        if self.numeric_columns:
            numeric_data = df[self.numeric_columns]
            row_sums = numeric_data.sum(axis=1)
            col_sums = numeric_data.sum(axis=0)

            self.metrics["total_transition_mass"] = float(numeric_data.sum().sum())
            self.metrics["min_row_mass"] = float(row_sums.min())
            self.metrics["max_row_mass"] = float(row_sums.max())
            self.metrics["mean_row_mass"] = float(row_sums.mean())
            self.metrics["min_column_mass"] = float(col_sums.min())
            self.metrics["max_column_mass"] = float(col_sums.max())
            self.metrics["mean_column_mass"] = float(col_sums.mean())

        self.log(
            f"Loaded transition matrix with {len(df)} rows and {len(df.columns)} columns."
        )

    def validate(self) -> None:
        self.log("Validating transition matrix.")

        if self.matrix is None:
            raise RuntimeError("No transition matrix loaded.")

        df = self.matrix

        self.validation_summary = {
            "rows": int(len(df)),
            "columns": int(len(df.columns)),
            "empty": bool(df.empty),
            "has_missing_values": bool(df.isna().any().any()),
            "column_names": list(df.columns),
            "numeric_columns": self.numeric_columns,
            "numeric_column_count": int(len(self.numeric_columns)),
        }

        if self.numeric_columns:
            numeric_data = df[self.numeric_columns]
            self.validation_summary["min_value"] = float(numeric_data.min().min())
            self.validation_summary["max_value"] = float(numeric_data.max().max())
            self.validation_summary["total_mass"] = float(numeric_data.sum().sum())

        self.metrics["has_missing_values"] = self.validation_summary[
            "has_missing_values"
        ]

        self.log("Transition matrix validation completed.")

    def generate_products(self) -> None:
        self.log("Generating transition matrix instrument products.")

        self.summary = {
            "instrument_id": self.instrument_id,
            "instrument_name": self.instrument_name,
            "instrument_category": self.instrument_category,
            "instrument_version": self.instrument_version,
            "input_file": str(self.matrix_path),
            "metrics": self.metrics,
            "validation": self.validation_summary,
        }

        if self.products_service is not None:
            summary_path = self.products_service.save_json(
                category=self.instrument_category,
                observatory_id=self.instrument_id.lower(),
                filename="transition_matrix_instrument_summary.json",
                data=self.summary,
            )

            product_root = self.products_service.product_root(
                self.instrument_category,
                self.instrument_id.lower(),
            )

            matrix_csv_path = product_root / "transition_matrix.csv"
            self.matrix.to_csv(matrix_csv_path, index=False)

            self.products["transition_matrix_summary"] = str(summary_path)
            self.products["transition_matrix_csv"] = str(matrix_csv_path)

            self.log(f"Saved transition matrix summary: {summary_path}")
            self.log(f"Saved transition matrix CSV: {matrix_csv_path}")

        else:
            self.log("No products service available; skipping product export.")

def main() -> None:
    from core.session import PrimeNetSession

    with PrimeNetSession(session_name="Transition Matrix Instrument Test") as session:
        instrument = TransitionMatrixInstrument(session=session)
        result = instrument.run()

        print()
        print("Transition Matrix Instrument completed successfully.")
        print(f"Status: {result.status}")
        print(f"Runtime: {result.runtime_sec:.3f} sec")
        print("Products:")
        for name, path in result.products.items():
            print(f"  {name}: {path}")


if __name__ == "__main__":
    main()
