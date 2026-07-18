from __future__ import annotations

import unittest

from observatories.entropy_rate import (
    build_entropy_rate_observation,
)
from observatories.framework import CoordinateRange


class EntropyObservationBuilderTests(unittest.TestCase):
    def make_summary(self) -> dict[str, object]:
        return {
            "instrument": "EntropyRateInstrument",
            "version": "1.0.0",
            "transition_matrix_path": (
                "products/results/transition/"
                "transition_matrix.csv"
            ),
            "stationary_distribution_path": (
                "products/results/transition/"
                "stationary_distribution.csv"
            ),
            "num_states": 20,
            "num_transitions_nonzero": 184,
            "matched_states": 20,
            "unmatched_states": 0,
            "total_stationary_mass_used": 1.0,
            "entropy_rate_bits_per_step": 3.125,
            "max_contribution_state": "6",
            "max_contribution_value": 0.42,
        }

    def test_builds_canonical_observation(self) -> None:
        observation = build_entropy_rate_observation(
            observation_id="OBS-entropy-test-0001",
            coordinate_range=CoordinateRange(
                coordinate_system="prime_index",
                start=1,
                end=1_000_000,
            ),
            summary=self.make_summary(),
            created_utc="2026-07-18T20:00:00Z",
        )

        self.assertEqual(
            observation.observatory_name,
            "Entropy Rate Observatory",
        )
        self.assertEqual(
            observation.coordinate_system,
            "prime_index",
        )
        self.assertEqual(
            observation.statistics[
                "entropy_rate_bits_per_step"
            ],
            3.125,
        )
        self.assertEqual(
            observation.measurements["num_states"],
            20,
        )
        self.assertEqual(
            observation.provenance["instrument"],
            "EntropyRateInstrument",
        )

    def test_observation_round_trip(self) -> None:
        observation = build_entropy_rate_observation(
            observation_id="OBS-entropy-test-0002",
            coordinate_range=CoordinateRange(
                coordinate_system="prime_index",
                start=1,
                end=1_000_000,
            ),
            summary=self.make_summary(),
            created_utc="2026-07-18T20:00:00Z",
        )

        restored = type(observation).from_dict(
            observation.to_dict()
        )

        self.assertEqual(restored, observation)

    def test_missing_summary_field_is_rejected(self) -> None:
        summary = self.make_summary()
        del summary["entropy_rate_bits_per_step"]

        with self.assertRaises(ValueError):
            build_entropy_rate_observation(
                observation_id="OBS-entropy-test-0003",
                coordinate_range=CoordinateRange(
                    coordinate_system="prime_index",
                    start=1,
                    end=100,
                ),
                summary=summary,
            )


if __name__ == "__main__":
    unittest.main()
