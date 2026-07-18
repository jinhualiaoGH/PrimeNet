from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping

from .observation import Observation


DOCUMENT_SCHEMA_VERSION = "primenet.observation.document/v1"
SOFTWARE_NAME = "PrimeNet"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True, slots=True)
class ObservationDocument:
    observation: Observation
    software_version: str
    created_utc: str = field(default_factory=_utc_now_iso)
    software_name: str = SOFTWARE_NAME
    document_schema_version: str = DOCUMENT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        if not isinstance(self.observation, Observation):
            raise TypeError("observation must be an Observation.")

        self.observation.validate()

        if not isinstance(self.software_name, str):
            raise TypeError("software_name must be a string.")

        if not self.software_name.strip():
            raise ValueError("software_name must not be empty.")

        if not isinstance(self.software_version, str):
            raise TypeError("software_version must be a string.")

        if not self.software_version.strip():
            raise ValueError("software_version must not be empty.")

        if not isinstance(self.created_utc, str):
            raise TypeError("created_utc must be a string.")

        if not self.created_utc.endswith("Z"):
            raise ValueError(
                "created_utc must be a UTC timestamp ending in 'Z'."
            )

        if self.document_schema_version != DOCUMENT_SCHEMA_VERSION:
            raise ValueError(
                "Unsupported document_schema_version: "
                f"{self.document_schema_version!r}. "
                f"Expected {DOCUMENT_SCHEMA_VERSION!r}."
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "document_schema_version": self.document_schema_version,
            "metadata": {
                "software_name": self.software_name,
                "software_version": self.software_version,
                "created_utc": self.created_utc,
            },
            "observation": self.observation.to_dict(),
        }

    @classmethod
    def from_dict(
        cls,
        payload: Mapping[str, Any],
    ) -> "ObservationDocument":
        if not isinstance(payload, Mapping):
            raise TypeError("payload must be a mapping.")

        required = {
            "document_schema_version",
            "metadata",
            "observation",
        }
        missing = required.difference(payload)

        if missing:
            missing_text = ", ".join(sorted(missing))
            raise ValueError(
                "ObservationDocument payload is missing: "
                f"{missing_text}."
            )

        metadata = payload["metadata"]
        if not isinstance(metadata, Mapping):
            raise ValueError("payload.metadata must be a mapping.")

        metadata_required = {
            "software_name",
            "software_version",
            "created_utc",
        }
        metadata_missing = metadata_required.difference(metadata)

        if metadata_missing:
            missing_text = ", ".join(sorted(metadata_missing))
            raise ValueError(
                "ObservationDocument metadata is missing: "
                f"{missing_text}."
            )

        observation_payload = payload["observation"]
        if not isinstance(observation_payload, Mapping):
            raise ValueError(
                "payload.observation must be a mapping."
            )

        return cls(
            observation=Observation.from_dict(observation_payload),
            software_name=str(metadata["software_name"]),
            software_version=str(metadata["software_version"]),
            created_utc=str(metadata["created_utc"]),
            document_schema_version=str(
                payload["document_schema_version"]
            ),
        )
