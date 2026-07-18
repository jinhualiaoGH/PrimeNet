from __future__ import annotations

import unittest

from observatories.framework import CoordinateRange, Observation
from observatories.information import (
    build_entropy_information_observation,
    build_geometry_information_observation,
    build_invariant_information_observation,
    build_taxonomy_information_observation,
    build_transition_information_observation,
)


class InformationObservationBuilderTests(unittest.TestCase):
    def make_range(self) -> CoordinateRange:
        return CoordinateRange(
            coordinate_system="numeric_value",
            start=1,
            end=1_000_000,
        )

    def base_summary(self, instrument: str, instrument_id: str) -> dict:
        return {
            "instrument": instrument,
            "instrument_id": instrument_id,
            "observatory": "Information Observatory",
            "version": "1.0.0",
            "created_utc": "2026-06-25T04:00:00+00:00",
            "start": 1,
            "end": 1_000_000,
            "runtime": {"total_seconds": 0.05, "total_minutes": 0.0008333333333333334},
            "python_version": "3.14.5",
            "platform": "Windows-11",
            "numpy_version": "2.4.6",
        }

    def test_entropy_adapter(self) -> None:
        summary = self.base_summary("entropy_observatory.py", "IO-001")
        summary.update({
            "gap": 6,
            "prime_count": 78_498,
            "gap_summary": {"gap_count": 78_497, "gap_min": 1, "gap_max": 114, "gap_mean": 12.739},
            "max_order": 5,
            "event_language_length": 78_497,
            "event_count": 13_549,
            "event_density": 0.17260532249640115,
            "orders": {"H0": {"entropy_bits": 0.6636300924487245}},
        })
        observation = build_entropy_information_observation(
            observation_id="OBS-info-entropy-0001",
            coordinate_range=self.make_range(),
            summary=summary,
            created_utc="2026-07-18T23:30:00Z",
        )
        self.assertIsInstance(observation, Observation)
        self.assertEqual(observation.measurements["event_count"], 13_549)
        self.assertEqual(observation.statistics["orders"]["H0"]["entropy_bits"], 0.6636300924487245)

    def test_transition_adapter(self) -> None:
        summary = self.base_summary("transition_observatory.py", "IO-002")
        summary.update({
            "prime_count": 78_498,
            "gap_count": 78_497,
            "selected_state_count": 20,
            "selected_states": [2, 4, 6],
            "total_selected_transitions": 75_310,
            "nonzero_source_rows": 20,
            "transition_matrix_density": 0.79,
            "spectral_summary": {"spectral_gap": 0.4396996654601447},
        })
        observation = build_transition_information_observation(
            observation_id="OBS-info-transition-0001",
            coordinate_range=self.make_range(),
            summary=summary,
        )
        self.assertEqual(observation.measurements["total_selected_transitions"], 75_310)
        self.assertEqual(observation.statistics["spectral_summary"]["spectral_gap"], 0.4396996654601447)

    def test_geometry_adapter(self) -> None:
        summary = self.base_summary("information_geometry_observatory.py", "IO-003")
        summary.update({
            "prime_count": 78_498,
            "gap_count": 78_497,
            "selected_state_count": 20,
            "selected_states": [2, 4, 6],
            "geometry_summary": {"linear_information_law": {"r2": 0.9125847845535676}},
        })
        observation = build_geometry_information_observation(
            observation_id="OBS-info-geometry-0001",
            coordinate_range=self.make_range(),
            summary=summary,
        )
        self.assertEqual(observation.statistics["geometry_summary"]["linear_information_law"]["r2"], 0.9125847845535676)

    def test_invariant_adapter(self) -> None:
        summary = self.base_summary("invariant_observatory.py", "IO-004")
        summary.update({
            "prime_count": 78_498,
            "gap_count": 78_497,
            "selected_state_count": 20,
            "selected_states": [2, 4, 6],
            "invariant_summary": {"candidate_invariants_ranked_by_stability": [{"name": "I4"}]},
        })
        observation = build_invariant_information_observation(
            observation_id="OBS-info-invariant-0001",
            coordinate_range=self.make_range(),
            summary=summary,
        )
        self.assertEqual(observation.statistics["invariant_summary"]["candidate_invariants_ranked_by_stability"][0]["name"], "I4")

    def test_taxonomy_adapter(self) -> None:
        summary = self.base_summary("taxonomy_observatory.py", "IO-005")
        summary.update({
            "top_n": 20,
            "even_only": True,
            "inputs": {"geometry_csv": "geometry.csv"},
            "taxonomy_summary": {
                "gap_count": 20,
                "taxonomy_counts": {"Core Resonant Gap": 3},
            },
        })
        observation = build_taxonomy_information_observation(
            observation_id="OBS-info-taxonomy-0001",
            coordinate_range=self.make_range(),
            summary=summary,
        )
        self.assertEqual(observation.measurements["classified_gap_count"], 20)
        self.assertEqual(observation.statistics["taxonomy_summary"]["taxonomy_counts"]["Core Resonant Gap"], 3)

    def test_round_trip(self) -> None:
        summary = self.base_summary("taxonomy_observatory.py", "IO-005")
        summary.update({
            "top_n": 20,
            "even_only": True,
            "inputs": {},
            "taxonomy_summary": {"gap_count": 20, "taxonomy_counts": {}},
        })
        original = build_taxonomy_information_observation(
            observation_id="OBS-info-roundtrip-0001",
            coordinate_range=self.make_range(),
            summary=summary,
            created_utc="2026-07-18T23:30:00Z",
        )
        self.assertEqual(Observation.from_dict(original.to_dict()), original)

    def test_wrong_range_is_rejected(self) -> None:
        summary = self.base_summary("taxonomy_observatory.py", "IO-005")
        summary.update({"top_n": 20, "even_only": True, "inputs": {}, "taxonomy_summary": {"gap_count": 20}})
        summary["end"] = 999_999
        with self.assertRaises(ValueError):
            build_taxonomy_information_observation(
                observation_id="OBS-info-range-0001",
                coordinate_range=self.make_range(),
                summary=summary,
            )

    def test_wrong_instrument_kind_is_rejected(self) -> None:
        summary = self.base_summary("transition_observatory.py", "IO-002")
        summary.update({
            "prime_count": 78_498,
            "gap_count": 78_497,
            "selected_state_count": 20,
            "selected_states": [2, 4, 6],
            "spectral_summary": {"spectral_gap": 0.44},
        })
        with self.assertRaises(ValueError):
            build_geometry_information_observation(
                observation_id="OBS-info-kind-0001",
                coordinate_range=self.make_range(),
                summary=summary,
            )


if __name__ == "__main__":
    unittest.main()
