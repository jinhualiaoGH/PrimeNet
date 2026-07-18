from __future__ import annotations

import unittest

from observatories.framework import (
    CoordinateRange,
    Observation,
    RANGE_SEMANTICS,
    SCHEMA_VERSION,
)


class CoordinateRangeContractTests(unittest.TestCase):
    def test_valid_inclusive_range(self) -> None:
        coordinate_range = CoordinateRange(
            coordinate_system="prime_index",
            start=1,
            end=100,
        )

        self.assertEqual(
            coordinate_range.semantics,
            RANGE_SEMANTICS,
        )
        self.assertEqual(coordinate_range.length, 100)
        self.assertTrue(coordinate_range.contains(1))
        self.assertTrue(coordinate_range.contains(100))
        self.assertFalse(coordinate_range.contains(101))

    def test_invalid_reverse_range_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            CoordinateRange(
                coordinate_system="prime_index",
                start=100,
                end=1,
            )

    def test_dictionary_round_trip(self) -> None:
        original = CoordinateRange(
            coordinate_system="prime_index",
            start=10,
            end=20,
        )

        restored = CoordinateRange.from_dict(
            original.to_dict()
        )

        self.assertEqual(restored, original)


class ObservationContractTests(unittest.TestCase):
    def make_observation(self) -> Observation:
        return Observation(
            observation_id="OBS-test-0001",
            observatory_name="framework_contract_test",
            title="Observation Core Contract Test",
            coordinate_range=CoordinateRange(
                coordinate_system="prime_index",
                start=1,
                end=100,
            ),
            parameters={"gap": 2},
            measurements={"count": 8},
            statistics={"density": 0.08},
            provenance={"source": "contract_test"},
            created_utc="2026-07-18T19:20:41Z",
        )

    def test_observation_round_trip(self) -> None:
        original = self.make_observation()
        payload = original.to_dict()
        restored = Observation.from_dict(payload)

        self.assertEqual(restored, original)
        self.assertEqual(
            restored.schema_version,
            SCHEMA_VERSION,
        )

    def test_coordinate_properties(self) -> None:
        observation = self.make_observation()

        self.assertEqual(
            observation.coordinate_system,
            "prime_index",
        )
        self.assertEqual(observation.range_start, 1)
        self.assertEqual(observation.range_end, 100)

    def test_invalid_schema_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            Observation(
                observation_id="OBS-test-0002",
                observatory_name="framework_contract_test",
                title="Invalid Schema Test",
                coordinate_range=CoordinateRange(
                    coordinate_system="prime_index",
                    start=1,
                    end=10,
                ),
                schema_version="primenet.observation/v999",
            )


if __name__ == "__main__":
    unittest.main()
