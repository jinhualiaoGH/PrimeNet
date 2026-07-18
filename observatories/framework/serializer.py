from __future__ import annotations

import json
from typing import Any

from .observation_document import ObservationDocument


class ObservationSerializer:
    """
    Convert ObservationDocument objects to and from canonical JSON.

    This component performs no file-system operations.
    """

    @staticmethod
    def to_json(document: ObservationDocument) -> str:
        if not isinstance(document, ObservationDocument):
            raise TypeError(
                "document must be an ObservationDocument."
            )

        document.validate()

        return json.dumps(
            document.to_dict(),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )

    @staticmethod
    def from_json(text: str) -> ObservationDocument:
        if not isinstance(text, str):
            raise TypeError("text must be a string.")

        if not text.strip():
            raise ValueError("text must not be empty.")

        payload: Any = json.loads(text)

        if not isinstance(payload, dict):
            raise ValueError(
                "Serialized observation document must be "
                "a JSON object."
            )

        return ObservationDocument.from_dict(payload)
