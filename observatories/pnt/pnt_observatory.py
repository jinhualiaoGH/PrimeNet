"""
PrimeNet Transition Observatory
PNT Observatory v1.6

Runs the Transition Instrument Suite:
    - TransitionMatrixInstrument
    - StationaryDistributionInstrument
    - SpectralGapInstrument
    - MixingTimeInstrument
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from core.observatory import PrimeNetObservatory

from instruments.transition.transition_matrix_instrument import (
    TransitionMatrixInstrument,
)
from instruments.transition.stationary_distribution_instrument import (
    StationaryDistributionInstrument,
)
from instruments.transition.spectral_gap_instrument import (
    SpectralGapInstrument,
)
from instruments.transition.mixing_time_instrument import (
    MixingTimeInstrument,
)


class PNTObservatory(PrimeNetObservatory):
    observatory_id = "PNT"
    observatory_name = "PrimeNet Transition Observatory"
    observatory_category = "transition"
    observatory_version = "1.6.0"

    def __init__(
        self,
        session=None,
        transition_matrix_path: str | Path | None = None,
    ) -> None:
        super().__init__(session=session)

        self.transition_matrix_path = transition_matrix_path
        self.instrument_results: dict[str, Any] = {}

    def prepare(self) -> None:
        self.logger.info("Preparing PNT multi-instrument observatory.")

        self.instruments = {
            "transition_matrix": TransitionMatrixInstrument(
                session=self.session,
                matrix_path=self.transition_matrix_path,
            ),
            "stationary_distribution": StationaryDistributionInstrument(
                session=self.session,
                matrix_path=self.transition_matrix_path,
            ),
            "spectral_gap": SpectralGapInstrument(
                session=self.session,
                matrix_path=self.transition_matrix_path,
            ),
            "mixing_time": MixingTimeInstrument(
                session=self.session,
                matrix_path=self.transition_matrix_path,
            ),
        }

        self.logger.info(
            f"Attached {len(self.instruments)} transition instruments."
        )

    def measure(self) -> None:
        self.logger.info("Running Transition Instrument Suite.")

        for key, instrument in self.instruments.items():
            self.logger.section(f"Instrument: {key}")
            result = instrument.run()
            self.instrument_results[key] = result

            self.metrics[f"{key}_status"] = result.status
            self.metrics[f"{key}_runtime_sec"] = float(result.runtime_sec)

            for metric_name, metric_value in result.metrics.items():
                self.metrics[f"{key}_{metric_name}"] = metric_value

    def validate(self) -> None:
        self.logger.info("Validating Transition Instrument Suite.")

        if not self.instrument_results:
            raise RuntimeError("No transition instruments were executed.")

        failed = [
            key
            for key, result in self.instrument_results.items()
            if result.status != "completed"
        ]

        if failed:
            raise RuntimeError(f"Failed instruments: {failed}")

        self.metrics["transition_suite_validation_passed"] = True
        self.metrics["transition_suite_instrument_count"] = len(
            self.instrument_results
        )

        self.logger.info("Transition Instrument Suite validation passed.")

    def generate_products(self) -> None:
        self.logger.info("Generating PNT observatory summary product.")

        instrument_product_map = {}
        instrument_metric_map = {}

        for key, result in self.instrument_results.items():
            instrument_product_map[key] = result.products
            instrument_metric_map[key] = result.metrics

            for product_name, product_path in result.products.items():
                self.products[f"{key}_{product_name}"] = str(product_path)

        summary = {
            "observatory_id": self.observatory_id,
            "observatory_name": self.observatory_name,
            "observatory_category": self.observatory_category,
            "observatory_version": self.observatory_version,
            "input_file": str(self.transition_matrix_path),
            "instrument_count": len(self.instrument_results),
            "instrument_metrics": instrument_metric_map,
            "instrument_products": instrument_product_map,
            "metrics": self.metrics,
            "products": self.products,
        }

        path = self.products_service.save_json(
            category=self.observatory_category,
            observatory_id=self.observatory_id,
            filename="pnt_transition_observatory_suite_summary.json",
            data=summary,
        )

        self.products["pnt_transition_observatory_suite_summary"] = str(path)

        self.logger.info(f"Saved PNT suite summary: {path}")


def main() -> None:
    obs = PNTObservatory()
    result = obs.run()

    print()
    print("PNT Transition Observatory Suite completed successfully.")
    print(f"Status: {result.status}")
    print(f"Runtime: {result.runtime_sec:.3f} sec")
    print("Products:")
    for name, path in result.products.items():
        print(f"  {name}: {path}")


if __name__ == "__main__":
    main()