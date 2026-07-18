from __future__ import annotations

import unittest

from observatories.framework import (
    CoordinateRange,
    Observation,
)
from observatories.transition import (
    build_transition_observation,
)


class TransitionObservationBuilderTests(unittest.TestCase):
    def make_coordinate_range(self) -> CoordinateRange:
        return CoordinateRange(
            coordinate_system="prime_index",
            start=1,
            end=1_000_000,
        )

    def make_matrix_summary(self) -> dict:
        return {
            "observatory_id": "OBS-TRANSITION",
            "observatory_name": "Transition Observatory",
            "observatory_category": "transition",
            "observatory_version": "1.0.0",
            "input_file": "transition_matrix.csv",
            "metrics": {
                "rows": 20,
                "columns": 21,
                "numeric_columns": 20,
                "total_matrix_mass": 1_000_000.0,
                "min_row_mass": 12_000.0,
                "max_row_mass": 81_000.0,
                "mean_row_mass": 50_000.0,
                "min_column_mass": 11_500.0,
                "max_column_mass": 82_000.0,
                "mean_column_mass": 50_000.0,
                "has_missing_values": False,
            },
            "validation": {
                "rows": 20,
                "columns": 21,
                "empty": False,
                "has_missing_values": False,
                "column_names": [
                    "state",
                    *[str(index) for index in range(20)],
                ],
                "numeric_columns": [
                    str(index) for index in range(20)
                ],
                "numeric_column_count": 20,
                "min_value": 0.0,
                "max_value": 25_000.0,
                "total_mass": 1_000_000.0,
            },
        }

    def test_builds_transition_observation(self) -> None:
        observation = build_transition_observation(
            observation_id="OBS-transition-test-0001",
            coordinate_range=self.make_coordinate_range(),
            matrix_summary=self.make_matrix_summary(),
            created_utc="2026-07-18T22:30:00Z",
        )

        self.assertIsInstance(observation, Observation)
        self.assertEqual(
            observation.observatory_name,
            "Transition Observatory",
        )
        self.assertEqual(
            observation.title,
            "Transition Matrix Observation",
        )
        self.assertEqual(
            observation.parameters["matrix_category"],
            "transition",
        )
        self.assertEqual(
            observation.measurements["rows"],
            20,
        )
        self.assertEqual(
            observation.measurements["columns"],
            21,
        )
        self.assertEqual(
            observation.statistics["total_matrix_mass"],
            1_000_000.0,
        )
        self.assertEqual(
            observation.provenance["source_observatory_id"],
            "OBS-TRANSITION",
        )

    def test_observation_round_trip(self) -> None:
        original = build_transition_observation(
            observation_id="OBS-transition-test-0002",
            coordinate_range=self.make_coordinate_range(),
            matrix_summary=self.make_matrix_summary(),
            created_utc="2026-07-18T22:30:00Z",
        )

        restored = Observation.from_dict(original.to_dict())

        self.assertEqual(restored, original)

    def test_wrong_observatory_identity_is_rejected(self) -> None:
        summary = self.make_matrix_summary()
        summary["observatory_id"] = "OBS-NOT-TRANSITION"

        with self.assertRaises(ValueError):
            build_transition_observation(
                observation_id="OBS-transition-test-0003",
                coordinate_range=self.make_coordinate_range(),
                matrix_summary=summary,
            )

    def test_missing_matrix_contract_field_is_rejected(self) -> None:
        summary = self.make_matrix_summary()
        del summary["validation"]

        with self.assertRaises(ValueError):
            build_transition_observation(
                observation_id="OBS-transition-test-0004",
                coordinate_range=self.make_coordinate_range(),
                matrix_summary=summary,
            )


if __name__ == "__main__":
    unittest.main()
