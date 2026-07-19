from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import shutil

from .observation_document import ObservationDocument
from .writer import ObservationWriter, ObservationWriteResult


_COLLECTION_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")


@dataclass(frozen=True, slots=True)
class ObservationPublishResult:
    """
    Result returned after publishing one canonical observation record.
    """

    collection: str
    observation_id: str
    observation_directory: Path
    write_result: ObservationWriteResult
    replaced_existing: bool

    def __post_init__(self) -> None:
        if not isinstance(self.collection, str):
            raise TypeError("collection must be a string.")

        if not self.collection:
            raise ValueError("collection must not be empty.")

        if not isinstance(self.observation_id, str):
            raise TypeError("observation_id must be a string.")

        if not self.observation_id:
            raise ValueError("observation_id must not be empty.")

        if not isinstance(self.observation_directory, Path):
            raise TypeError(
                "observation_directory must be a pathlib.Path."
            )

        if not isinstance(self.write_result, ObservationWriteResult):
            raise TypeError(
                "write_result must be an ObservationWriteResult."
            )

        if not isinstance(self.replaced_existing, bool):
            raise TypeError(
                "replaced_existing must be a boolean."
            )


class ObservationRepository:
    """
    Publish canonical ObservationDocument records into a repository.

    Repository layout:

        <root>/
            <collection>/
                <observation_id>/
                    observation.json

    Existing observation records are protected unless overwrite=True.
    """

    def __init__(self, root: str | Path) -> None:
        if not isinstance(root, (str, Path)):
            raise TypeError(
                "root must be a string or pathlib.Path."
            )

        root_path = Path(root)

        if not str(root_path).strip():
            raise ValueError("root must not be empty.")

        self._root = root_path

    @property
    def root(self) -> Path:
        return self._root

    @staticmethod
    def _validate_collection(collection: str) -> str:
        if not isinstance(collection, str):
            raise TypeError("collection must be a string.")

        normalized = collection.strip()

        if not normalized:
            raise ValueError("collection must not be empty.")

        if not _COLLECTION_PATTERN.fullmatch(normalized):
            raise ValueError(
                "collection must contain only letters, numbers, "
                "underscores, or hyphens, and must begin with "
                "a letter or number."
            )

        return normalized

    @staticmethod
    def _validate_observation_id(observation_id: str) -> str:
        if not isinstance(observation_id, str):
            raise TypeError("observation_id must be a string.")

        normalized = observation_id.strip()

        if not normalized:
            raise ValueError(
                "observation_id must not be empty."
            )

        observation_path = Path(normalized)

        if (
            observation_path.is_absolute()
            or observation_path.name != normalized
            or normalized in {".", ".."}
        ):
            raise ValueError(
                "observation_id must be a simple directory name "
                "without path components."
            )

        return normalized

    def observation_directory(
        self,
        *,
        collection: str,
        observation_id: str,
    ) -> Path:
        collection_name = self._validate_collection(collection)
        record_id = self._validate_observation_id(
            observation_id
        )

        return self.root / collection_name / record_id

    def publish(
        self,
        *,
        document: ObservationDocument,
        collection: str,
        overwrite: bool = False,
    ) -> ObservationPublishResult:
        if not isinstance(document, ObservationDocument):
            raise TypeError(
                "document must be an ObservationDocument."
            )

        if not isinstance(overwrite, bool):
            raise TypeError("overwrite must be a boolean.")

        document.validate()

        collection_name = self._validate_collection(collection)
        observation_id = self._validate_observation_id(
            document.observation.observation_id
        )

        target_directory = self.observation_directory(
            collection=collection_name,
            observation_id=observation_id,
        )

        replaced_existing = target_directory.exists()

        if replaced_existing and not overwrite:
            raise FileExistsError(
                "Observation record already exists: "
                f"{target_directory}"
            )

        if replaced_existing:
            if not target_directory.is_dir():
                raise ValueError(
                    "Observation target exists but is not a "
                    f"directory: {target_directory}"
                )

            shutil.rmtree(target_directory)

        write_result = ObservationWriter.write(
            document=document,
            output_directory=target_directory,
        )

        return ObservationPublishResult(
            collection=collection_name,
            observation_id=observation_id,
            observation_directory=target_directory,
            write_result=write_result,
            replaced_existing=replaced_existing,
        )
