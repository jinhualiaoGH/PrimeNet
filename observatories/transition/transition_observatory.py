"""
PrimeNet Matrix Observatory

Intermediate base class for observatories that operate on matrix-like data.

Examples:
    - transition matrices
    - flow matrices
    - validation matrices
    - correlation matrices
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from core.observatory import PrimeNetObservatory


class MatrixObservatory(PrimeNetObservatory):
    """
    Intermediate base class for matrix-based PrimeNet observatories.
    """

    observatory_category = "matrix"
    default_matrix_path: Path | None = None

    def __init__(
        self,
        session=None,
        matrix_path: str | Path | None = None,
    ) -> None:
        super().__init__(session=session)

        self.matrix_path = Path(matrix_path) if matrix_path is not None else None
        self.matrix: pd.DataFrame | None = None
        self.matrix_numeric_columns: list[str] = []
        self.matrix_validation: dict[str, Any] = {}
        self.matrix_summary: dict[str, Any] = {}

    def prepare(self) -> None:
        self.logger.info("Preparing matrix observatory.")

        if self.matrix_path is None:
            if self.default_matrix_path is None:
                raise ValueError(
                    "No matrix_path provided and no default_matrix_path defined."
                )
            self.matrix_path = self.default_matrix_path

        self.matrix_path = Path(self.matrix_path)

        self.logger.info(f"Matrix path: {self.matrix_path}")

        if not self.matrix_path.exists():
            raise FileNotFoundError(f"Matrix file not found: {self.matrix_path}")

    def measure(self) -> None:
        self.logger.info("Loading matrix.")

        df = pd.read_csv(self.matrix_path)

        if df.empty:
            raise ValueError(f"Matrix file is empty: {self.matrix_path}")

        self.matrix = df
        self.matrix_numeric_columns = df.select_dtypes(
            include="number"
        ).columns.tolist()

        self.metrics["rows"] = int(len(df))
        self.metrics["columns"] = int(len(df.columns))
        self.metrics["numeric_columns"] = int(len(self.matrix_numeric_columns))

        if self.matrix_numeric_columns:
            numeric_data = df[self.matrix_numeric_columns]
            row_sums = numeric_data.sum(axis=1)
            col_sums = numeric_data.sum(axis=0)

            self.metrics["total_matrix_mass"] = float(numeric_data.sum().sum())
            self.metrics["min_row_mass"] = float(row_sums.min())
            self.metrics["max_row_mass"] = float(row_sums.max())
            self.metrics["mean_row_mass"] = float(row_sums.mean())
            self.metrics["min_column_mass"] = float(col_sums.min())
            self.metrics["max_column_mass"] = float(col_sums.max())
            self.metrics["mean_column_mass"] = float(col_sums.mean())

        self.logger.info(
            f"Loaded matrix with {len(df)} rows and {len(df.columns)} columns."
        )

    def validate(self) -> None:
        self.logger.info("Validating matrix.")

        if self.matrix is None:
            raise RuntimeError("No matrix loaded.")

        df = self.matrix

        self.matrix_validation = {
            "rows": int(len(df)),
            "columns": int(len(df.columns)),
            "empty": bool(df.empty),
            "has_missing_values": bool(df.isna().any().any()),
            "column_names": list(df.columns),
            "numeric_columns": self.matrix_numeric_columns,
            "numeric_column_count": int(len(self.matrix_numeric_columns)),
        }

        if self.matrix_numeric_columns:
            numeric_data = df[self.matrix_numeric_columns]

            self.matrix_validation["min_value"] = float(numeric_data.min().min())
            self.matrix_validation["max_value"] = float(numeric_data.max().max())
            self.matrix_validation["total_mass"] = float(numeric_data.sum().sum())

        self.metrics["has_missing_values"] = self.matrix_validation[
            "has_missing_values"
        ]

        self.logger.info("Matrix validation completed.")

    def generate_products(self) -> None:
        self.logger.info("Generating matrix observatory products.")

        if self.matrix is None:
            raise RuntimeError("No matrix loaded.")

        self.matrix_summary = {
            "observatory_id": self.observatory_id,
            "observatory_name": self.observatory_name,
            "observatory_category": self.observatory_category,
            "observatory_version": self.observatory_version,
            "input_file": str(self.matrix_path),
            "metrics": self.metrics,
            "validation": self.matrix_validation,
        }

        summary_path = self.products_service.save_json(
            category=self.observatory_category,
            observatory_id=self.observatory_id,
            filename="matrix_summary.json",
            data=self.matrix_summary,
        )

        self.products["matrix_summary"] = str(summary_path)
        self.logger.info(f"Saved matrix summary: {summary_path}")


def main() -> None:
    print("PrimeNet MatrixObservatory base class loaded successfully.")
    print("This module defines shared infrastructure for matrix observatories.")


if __name__ == "__main__":
    main()