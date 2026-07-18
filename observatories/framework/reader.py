from __future__ import annotations

from pathlib import Path

from .observation_document import ObservationDocument
from .serializer import ObservationSerializer
from .writer import DEFAULT_FILENAME


class ObservationReader:
    """
    Read one canonical observation document from disk.

    This layer handles file-system access only. JSON parsing and
    document reconstruction are delegated to ObservationSerializer.
    """

    @staticmethod
    def read(
        input_directory: str | Path,
        filename: str = DEFAULT_FILENAME,
    ) -> ObservationDocument:
        if not isinstance(input_directory, (str, Path)):
            raise TypeError(
                "input_directory must be a string or pathlib.Path."
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

        input_path = Path(input_directory) / filename

        if not input_path.exists():
            raise FileNotFoundError(
                f"Observation document does not exist: {input_path}"
            )

        if not input_path.is_file():
            raise ValueError(
                f"Observation document path is not a file: {input_path}"
            )

        text = input_path.read_text(encoding="utf-8")

        return ObservationSerializer.from_json(text)
