from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .observation_document import ObservationDocument
from .serializer import ObservationSerializer


DEFAULT_FILENAME = "observation.json"


@dataclass(frozen=True, slots=True)
class ObservationWriteResult:
    """
    Result returned after writing an observation document.
    """

    output_path: Path
    bytes_written: int

    def __post_init__(self) -> None:
        if not isinstance(self.output_path, Path):
            raise TypeError("output_path must be a pathlib.Path.")

        if not isinstance(self.bytes_written, int):
            raise TypeError("bytes_written must be an integer.")

        if self.bytes_written < 0:
            raise ValueError("bytes_written must not be negative.")


class ObservationWriter:
    """
    Persist one ObservationDocument as canonical UTF-8 JSON.

    This layer intentionally writes only the observation document.
    Manifests, checksums, indexes, and bundles belong to later
    framework components.
    """

    @staticmethod
    def write(
        document: ObservationDocument,
        output_directory: str | Path,
        filename: str = DEFAULT_FILENAME,
    ) -> ObservationWriteResult:
        if not isinstance(document, ObservationDocument):
            raise TypeError(
                "document must be an ObservationDocument."
            )

        if not isinstance(output_directory, (str, Path)):
            raise TypeError(
                "output_directory must be a string or pathlib.Path."
            )

        if not isinstance(filename, str):
            raise TypeError("filename must be a string.")

        if not filename.strip():
            raise ValueError("filename must not be empty.")

        filename_path = Path(filename)

        if filename_path.is_absolute() or filename_path.name != filename:
            raise ValueError(
                "filename must be a simple file name without "
                "directory components."
            )

        document.validate()

        directory = Path(output_directory)
        directory.mkdir(parents=True, exist_ok=True)

        output_path = directory / filename

        json_text = ObservationSerializer.to_json(document)
        encoded = json_text.encode("utf-8")

        output_path.write_bytes(encoded)

        return ObservationWriteResult(
            output_path=output_path,
            bytes_written=len(encoded),
        )
