from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from observatories.framework import (
    CoordinateRange,
    DEFAULT_FILENAME,
    Observation,
    ObservationDocument,
    ObservationSerializer,
    ObservationWriter,
    ObservationWriteResult,
)


class ObservationWriterTests(unittest.TestCase):
    def make_document(self) -> ObservationDocument:
        observation = Observation(
            observation_id="OBS-writer-test-0001",
            observatory_name="framework_contract_test",
            title="Observation Writer Contract Test",
            coordinate_range=CoordinateRange(
                coordinate_system="prime_index",
                start=1,
                end=1_000,
            ),
            parameters={"gap": 2},
            measurements={"count": 35},
            statistics={"density": 0.035},
            provenance={"source": "writer_contract_test"},
            created_utc="2026-07-18T20:00:00Z",
        )

        return ObservationDocument(
            observation=observation,
            software_version="1.1.0-dev",
            created_utc="2026-07-18T20:01:00Z",
        )

    def test_creates_default_observation_file(self) -> None:
        document = self.make_document()

        with tempfile.TemporaryDirectory() as temp_directory:
            result = ObservationWriter.write(
                document=document,
                output_directory=temp_directory,
            )

            expected_path = (
                Path(temp_directory) / DEFAULT_FILENAME
            )

            self.assertIsInstance(
                result,
                ObservationWriteResult,
            )
            self.assertEqual(result.output_path, expected_path)
            self.assertTrue(expected_path.is_file())
            self.assertEqual(
                result.bytes_written,
                expected_path.stat().st_size,
            )

    def test_written_document_round_trip(self) -> None:
        document = self.make_document()

        with tempfile.TemporaryDirectory() as temp_directory:
            result = ObservationWriter.write(
                document=document,
                output_directory=temp_directory,
            )

            restored = ObservationSerializer.from_json(
                result.output_path.read_text(encoding="utf-8")
            )

            self.assertEqual(restored, document)

    def test_repeated_write_is_idempotent(self) -> None:
        document = self.make_document()

        with tempfile.TemporaryDirectory() as temp_directory:
            first_result = ObservationWriter.write(
                document=document,
                output_directory=temp_directory,
            )
            first_bytes = first_result.output_path.read_bytes()

            second_result = ObservationWriter.write(
                document=document,
                output_directory=temp_directory,
            )
            second_bytes = second_result.output_path.read_bytes()

            self.assertEqual(
                first_result.output_path,
                second_result.output_path,
            )
            self.assertEqual(first_bytes, second_bytes)
            self.assertEqual(
                first_result.bytes_written,
                second_result.bytes_written,
            )

    def test_creates_nested_output_directories(self) -> None:
        document = self.make_document()

        with tempfile.TemporaryDirectory() as temp_directory:
            nested_directory = (
                Path(temp_directory)
                / "level_one"
                / "level_two"
                / "level_three"
            )

            result = ObservationWriter.write(
                document=document,
                output_directory=nested_directory,
            )

            self.assertTrue(nested_directory.is_dir())
            self.assertTrue(result.output_path.is_file())
            self.assertEqual(
                result.output_path.parent,
                nested_directory,
            )


if __name__ == "__main__":
    unittest.main()
