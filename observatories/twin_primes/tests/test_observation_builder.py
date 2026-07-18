from __future__ import annotations

import unittest

from observatories.framework import CoordinateRange, Observation
from observatories.twin_primes import build_twin_prime_observation


class TwinPrimeObservationBuilderTests(unittest.TestCase):
    def make_coordinate_range(self) -> CoordinateRange:
        return CoordinateRange(
            coordinate_system="numeric_value",
            start=1,
            end=3_000_000_000_000,
        )

    def make_summary(self) -> dict:
        return {
            "project": "PrimeNet",
            "instrument": "Twin Prime Census",
            "version": "1.0.0",
            "repository": r"E:\PrimeNet\Repository\gaps_u16_v3",
            "repository_status": "ACCEPTED",
            "numeric_domain_start": 1,
            "numeric_domain_end": 3_000_000_000_000,
            "event_definition": "g(i) = 2",
            "gap_files_scanned": 300,
            "total_gaps_scanned": 108_340_298_703,
            "total_twin_prime_events": 5_173_760_785,
            "global_twin_density": 0.04775472143734025,
            "runtime_seconds": 2870.0099790000095,
            "runtime_minutes": 47.83349965000016,
            "csv_output": (
                "E:\\PrimeNet\\Repository\\observations\\twin_primes\\"
                "twin_prime_census_1_3T.csv"
            ),
            "generated_at_utc": "2026-07-10T10:17:29.313194+00:00",
        }

    def test_builds_canonical_twin_prime_observation(self) -> None:
        observation = build_twin_prime_observation(
            observation_id="OBS-twin-prime-test-0001",
            coordinate_range=self.make_coordinate_range(),
            summary=self.make_summary(),
            created_utc="2026-07-18T23:00:00Z",
        )

        self.assertIsInstance(observation, Observation)
        self.assertEqual(
            observation.observatory_name,
            "Twin Prime Observatory",
        )
        self.assertEqual(
            observation.title,
            "Twin Prime Census Observation",
        )
        self.assertEqual(
            observation.parameters["event_definition"],
            "g(i) = 2",
        )
        self.assertEqual(
            observation.measurements["total_gaps_scanned"],
            108_340_298_703,
        )
        self.assertEqual(
            observation.measurements["total_twin_prime_events"],
            5_173_760_785,
        )
        self.assertEqual(
            observation.statistics["global_twin_density"],
            0.04775472143734025,
        )
        self.assertEqual(
            observation.provenance["repository_status"],
            "ACCEPTED",
        )
        self.assertEqual(
            observation.provenance["source_generated_at_utc"],
            "2026-07-10T10:17:29.313194Z",
        )

    def test_observation_round_trip(self) -> None:
        original = build_twin_prime_observation(
            observation_id="OBS-twin-prime-test-0002",
            coordinate_range=self.make_coordinate_range(),
            summary=self.make_summary(),
            created_utc="2026-07-18T23:00:00Z",
        )

        restored = Observation.from_dict(original.to_dict())

        self.assertEqual(restored, original)

    def test_missing_summary_field_is_rejected(self) -> None:
        summary = self.make_summary()
        del summary["total_twin_prime_events"]

        with self.assertRaises(ValueError):
            build_twin_prime_observation(
                observation_id="OBS-twin-prime-test-0003",
                coordinate_range=self.make_coordinate_range(),
                summary=summary,
            )

    def test_wrong_event_definition_is_rejected(self) -> None:
        summary = self.make_summary()
        summary["event_definition"] = "g(i) = 4"

        with self.assertRaises(ValueError):
            build_twin_prime_observation(
                observation_id="OBS-twin-prime-test-0004",
                coordinate_range=self.make_coordinate_range(),
                summary=summary,
            )

    def test_coordinate_range_mismatch_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            build_twin_prime_observation(
                observation_id="OBS-twin-prime-test-0005",
                coordinate_range=CoordinateRange(
                    coordinate_system="numeric_value",
                    start=1,
                    end=1_000_000_000_000,
                ),
                summary=self.make_summary(),
            )

    def test_inconsistent_density_is_rejected(self) -> None:
        summary = self.make_summary()
        summary["global_twin_density"] = 0.05

        with self.assertRaises(ValueError):
            build_twin_prime_observation(
                observation_id="OBS-twin-prime-test-0006",
                coordinate_range=self.make_coordinate_range(),
                summary=summary,
            )


if __name__ == "__main__":
    unittest.main()
