from __future__ import annotations

import json
import unittest

from observatories.framework import (
    CoordinateRange,
    DOCUMENT_SCHEMA_VERSION,
    Observation,
    ObservationDocument,
    ObservationSerializer,
)


class ObservationDocumentTests(unittest.TestCase):
    def make_observation(self) -> Observation:
        return Observation(
            observation_id="OBS-document-test-0001",
            observatory_name="framework_contract_test",
            title="Observation Document Contract Test",
            coordinate_range=CoordinateRange(
                coordinate_system="prime_index",
                start=1,
                end=1_000,
            ),
            parameters={"gap": 2},
            measurements={"count": 35},
            statistics={"density": 0.035},
            provenance={"source": "contract_test"},
            created_utc="2026-07-18T20:00:00Z",
        )

    def make_document(self) -> ObservationDocument:
        return ObservationDocument(
            observation=self.make_observation(),
            software_version="1.1.0-dev",
            created_utc="2026-07-18T20:01:00Z",
        )

    def test_document_round_trip(self) -> None:
        original = self.make_document()
        restored = ObservationDocument.from_dict(
            original.to_dict()
        )

        self.assertEqual(restored, original)
        self.assertEqual(
            restored.document_schema_version,
            DOCUMENT_SCHEMA_VERSION,
        )

    def test_json_round_trip(self) -> None:
        original = self.make_document()

        text = ObservationSerializer.to_json(original)
        restored = ObservationSerializer.from_json(text)

        self.assertEqual(restored, original)

    def test_serialization_is_deterministic(self) -> None:
        document = self.make_document()

        first = ObservationSerializer.to_json(document)
        second = ObservationSerializer.to_json(document)

        self.assertEqual(first, second)

    def test_serialized_json_has_sorted_keys(self) -> None:
        text = ObservationSerializer.to_json(
            self.make_document()
        )

        payload = json.loads(text)

        self.assertEqual(
            list(payload),
            [
                "document_schema_version",
                "metadata",
                "observation",
            ],
        )

    def test_malformed_json_is_rejected(self) -> None:
        with self.assertRaises(json.JSONDecodeError):
            ObservationSerializer.from_json(
                '{"document_schema_version":'
            )

    def test_non_object_json_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            ObservationSerializer.from_json("[1, 2, 3]")

    def test_invalid_document_schema_is_rejected(self) -> None:
        payload = self.make_document().to_dict()
        payload["document_schema_version"] = (
            "primenet.observation.document/v999"
        )

        text = json.dumps(payload)

        with self.assertRaises(ValueError):
            ObservationSerializer.from_json(text)

    def test_non_finite_values_are_rejected(self) -> None:
        observation = Observation(
            observation_id="OBS-document-test-0002",
            observatory_name="framework_contract_test",
            title="Non-Finite Value Test",
            coordinate_range=CoordinateRange(
                coordinate_system="prime_index",
                start=1,
                end=10,
            ),
            statistics={"value": float("nan")},
            created_utc="2026-07-18T20:00:00Z",
        )

        document = ObservationDocument(
            observation=observation,
            software_version="1.1.0-dev",
            created_utc="2026-07-18T20:01:00Z",
        )

        with self.assertRaises(ValueError):
            ObservationSerializer.to_json(document)


if __name__ == "__main__":
    unittest.main()
