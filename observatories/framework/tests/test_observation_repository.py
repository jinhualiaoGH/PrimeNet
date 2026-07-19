from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from observatories.framework import (
    CoordinateRange,
    Observation,
    ObservationDocument,
    ObservationPublishResult,
    ObservationReader,
    ObservationRepository,
)


class ObservationRepositoryTests(unittest.TestCase):
    def make_document(
        self,
        observation_id: str = "OBS-repository-test-0001",
    ) -> ObservationDocument:
        observation = Observation(
            observation_id=observation_id,
            observatory_name="repository_contract_test",
            title="Observation Repository Contract Test",
            coordinate_range=CoordinateRange(
                coordinate_system="prime_index",
                start=1,
                end=1_000,
            ),
            parameters={"gap": 2},
            measurements={"count": 35},
            statistics={"density": 0.035},
            provenance={"source": "repository_contract_test"},
            created_utc="2026-07-18T23:45:00Z",
        )

        return ObservationDocument(
            observation=observation,
            software_version="1.2.0-dev",
            created_utc="2026-07-18T23:46:00Z",
        )

    def test_publishes_canonical_repository_record(self) -> None:
        document = self.make_document()

        with tempfile.TemporaryDirectory() as temp_directory:
            repository = ObservationRepository(temp_directory)

            result = repository.publish(
                document=document,
                collection="twin_primes",
            )

            expected_directory = (
                Path(temp_directory)
                / "twin_primes"
                / document.observation.observation_id
            )

            self.assertIsInstance(
                result,
                ObservationPublishResult,
            )
            self.assertEqual(
                result.observation_directory,
                expected_directory,
            )
            self.assertEqual(
                result.write_result.output_path,
                expected_directory / "observation.json",
            )
            self.assertTrue(
                result.write_result.output_path.is_file()
            )
            self.assertFalse(result.replaced_existing)

    def test_published_record_round_trip(self) -> None:
        document = self.make_document()

        with tempfile.TemporaryDirectory() as temp_directory:
            repository = ObservationRepository(temp_directory)

            result = repository.publish(
                document=document,
                collection="entropy_rate",
            )

            restored = ObservationReader.read(
                result.observation_directory
            )

            self.assertEqual(restored, document)

    def test_existing_record_is_protected_by_default(self) -> None:
        document = self.make_document()

        with tempfile.TemporaryDirectory() as temp_directory:
            repository = ObservationRepository(temp_directory)

            repository.publish(
                document=document,
                collection="information",
            )

            with self.assertRaises(FileExistsError):
                repository.publish(
                    document=document,
                    collection="information",
                )

    def test_explicit_overwrite_replaces_record(self) -> None:
        first_document = self.make_document()
        second_document = ObservationDocument(
            observation=Observation(
                observation_id=(
                    first_document.observation.observation_id
                ),
                observatory_name="repository_contract_test",
                title="Replacement Observation",
                coordinate_range=CoordinateRange(
                    coordinate_system="prime_index",
                    start=1,
                    end=2_000,
                ),
                measurements={"count": 70},
                statistics={"density": 0.035},
                provenance={"source": "replacement_test"},
                created_utc="2026-07-18T23:47:00Z",
            ),
            software_version="1.2.0-dev",
            created_utc="2026-07-18T23:48:00Z",
        )

        with tempfile.TemporaryDirectory() as temp_directory:
            repository = ObservationRepository(temp_directory)

            repository.publish(
                document=first_document,
                collection="transition",
            )

            result = repository.publish(
                document=second_document,
                collection="transition",
                overwrite=True,
            )

            restored = ObservationReader.read(
                result.observation_directory
            )

            self.assertTrue(result.replaced_existing)
            self.assertEqual(restored, second_document)

    def test_invalid_collection_is_rejected(self) -> None:
        document = self.make_document()

        with tempfile.TemporaryDirectory() as temp_directory:
            repository = ObservationRepository(temp_directory)

            for invalid_collection in (
                "",
                " ",
                "../escape",
                "bad/name",
                "bad name",
            ):
                with self.subTest(
                    collection=invalid_collection
                ):
                    with self.assertRaises(ValueError):
                        repository.publish(
                            document=document,
                            collection=invalid_collection,
                        )

    def test_observation_id_path_escape_is_rejected(self) -> None:
        document = self.make_document(
            observation_id="../escape"
        )

        with tempfile.TemporaryDirectory() as temp_directory:
            repository = ObservationRepository(temp_directory)

            with self.assertRaises(ValueError):
                repository.publish(
                    document=document,
                    collection="twin_primes",
                )


if __name__ == "__main__":
    unittest.main()
