from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping

from .coordinate_range import CoordinateRange


SCHEMA_VERSION = "primenet.observation/v1"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _ensure_mapping(
    name: str,
    value: Mapping[str, Any],
) -> None:
    if not isinstance(value, Mapping):
        raise TypeError(f"{name} must be a mapping.")


@dataclass(frozen=True, slots=True)
class Observation:
    observation_id: str
    observatory_name: str
    title: str
    coordinate_range: CoordinateRange
    parameters: Mapping[str, Any] = field(default_factory=dict)
    measurements: Mapping[str, Any] = field(default_factory=dict)
    statistics: Mapping[str, Any] = field(default_factory=dict)
    provenance: Mapping[str, Any] = field(default_factory=dict)
    created_utc: str = field(default_factory=_utc_now_iso)
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        self.validate()

    @property
    def coordinate_system(self) -> str:
        return self.coordinate_range.coordinate_system

    @property
    def range_start(self) -> int:
        return self.coordinate_range.start

    @property
    def range_end(self) -> int:
        return self.coordinate_range.end

    def validate(self) -> None:
        if not isinstance(self.observation_id, str):
            raise TypeError("observation_id must be a string.")

        if not self.observation_id.strip():
            raise ValueError("observation_id must not be empty.")

        if not isinstance(self.observatory_name, str):
            raise TypeError("observatory_name must be a string.")

        if not self.observatory_name.strip():
            raise ValueError("observatory_name must not be empty.")

        if not isinstance(self.title, str):
            raise TypeError("title must be a string.")

        if not self.title.strip():
            raise ValueError("title must not be empty.")

        if not isinstance(self.coordinate_range, CoordinateRange):
            raise TypeError(
                "coordinate_range must be a CoordinateRange."
            )

        self.coordinate_range.validate()

        _ensure_mapping("parameters", self.parameters)
        _ensure_mapping("measurements", self.measurements)
        _ensure_mapping("statistics", self.statistics)
        _ensure_mapping("provenance", self.provenance)

        if self.schema_version != SCHEMA_VERSION:
            raise ValueError(
                f"Unsupported schema_version: "
                f"{self.schema_version!r}. "
                f"Expected {SCHEMA_VERSION!r}."
            )

        if not isinstance(self.created_utc, str):
            raise TypeError("created_utc must be a string.")

        if not self.created_utc.endswith("Z"):
            raise ValueError(
                "created_utc must be a UTC timestamp ending in 'Z'."
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "observation_id": self.observation_id,
            "observatory_name": self.observatory_name,
            "title": self.title,
            "coordinate_range": self.coordinate_range.to_dict(),
            "parameters": dict(self.parameters),
            "measurements": dict(self.measurements),
            "statistics": dict(self.statistics),
            "provenance": dict(self.provenance),
            "created_utc": self.created_utc,
        }

    @classmethod
    def from_dict(
        cls,
        payload: Mapping[str, Any],
    ) -> "Observation":
        _ensure_mapping("payload", payload)

        required = {
            "schema_version",
            "observation_id",
            "observatory_name",
            "title",
            "coordinate_range",
            "created_utc",
        }
        missing = required.difference(payload)

        if missing:
            missing_text = ", ".join(sorted(missing))
            raise ValueError(
                f"Observation payload is missing: {missing_text}."
            )

        range_payload = payload["coordinate_range"]
        if not isinstance(range_payload, Mapping):
            raise ValueError(
                "payload.coordinate_range must be a mapping."
            )

        return cls(
            observation_id=str(payload["observation_id"]),
            observatory_name=str(payload["observatory_name"]),
            title=str(payload["title"]),
            coordinate_range=CoordinateRange.from_dict(
                range_payload
            ),
            parameters=payload.get("parameters", {}),
            measurements=payload.get("measurements", {}),
            statistics=payload.get("statistics", {}),
            provenance=payload.get("provenance", {}),
            created_utc=str(payload["created_utc"]),
            schema_version=str(payload["schema_version"]),
        )
