from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from observatories.framework import (
    CoordinateRange,
    Observation,
    ObservationDocument,
    ObservationReader,
    ObservationWriter,
)


class ObservationReaderTests(unittest.TestCase):
    def make_document(self) -> ObservationDocument:
        observation = Observation(
            observation_id="OBS-reader-test-0001",
            observatory_name="framework_contract_test",
            title="Observation Reader Contract Test",
            coordinate_range=CoordinateRange(
                coordinate_system="prime_index",
                start=1,
                end=1_000,
            ),
            parameters={"gap": 2},
            measurements={"count": 35},
            statistics={"density": 0.035},
            provenance={"source": "reader_contract_test"},
            created_utc="2026-07-18T21:00:00Z",
        )

        return ObservationDocument(
            observation=observation,
            software_version="1.1.0-dev",
            created_utc="2026-07-18T21:01:00Z",
        )

    def test_read_after_write_round_trip(self) -> None:
        original = self.make_document()

        with tempfile.TemporaryDirectory() as temp_directory:
            ObservationWriter.write(
                document=original,
                output_directory=temp_directory,
            )

            restored = ObservationReader.read(temp_directory)

            self.assertEqual(restored, original)

    def test_missing_file_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_directory:
            with self.assertRaises(FileNotFoundError):
                ObservationReader.read(temp_directory)

    def test_malformed_json_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_directory:
            output_path = (
                Path(temp_directory) / "observation.json"
            )

            output_path.write_text(
                '{"document_schema_version":',
                encoding="utf-8",
            )

            with self.assertRaises(json.JSONDecodeError):
                ObservationReader.read(temp_directory)

    def test_invalid_document_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_directory:
            output_path = (
                Path(temp_directory) / "observation.json"
            )

            output_path.write_text(
                json.dumps(
                    {
                        "document_schema_version":
                            "primenet.observation.document/v1",
                        "metadata": {
                            "software_name": "PrimeNet",
                            "software_version": "1.1.0-dev",
                            "created_utc":
                                "2026-07-18T21:01:00Z",
                        },
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaises(ValueError):
                ObservationReader.read(temp_directory)


if __name__ == "__main__":
    unittest.main()
