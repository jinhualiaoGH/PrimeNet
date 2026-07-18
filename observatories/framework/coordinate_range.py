from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


RANGE_SEMANTICS = "inclusive"


@dataclass(frozen=True, slots=True)
class CoordinateRange:
    coordinate_system: str
    start: int
    end: int
    semantics: str = RANGE_SEMANTICS

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        if not isinstance(self.coordinate_system, str):
            raise TypeError("coordinate_system must be a string.")

        if not self.coordinate_system.strip():
            raise ValueError("coordinate_system must not be empty.")

        if isinstance(self.start, bool) or not isinstance(self.start, int):
            raise TypeError("start must be an integer.")

        if isinstance(self.end, bool) or not isinstance(self.end, int):
            raise TypeError("end must be an integer.")

        if self.start > self.end:
            raise ValueError(
                "start must be less than or equal to end."
            )

        if self.semantics != RANGE_SEMANTICS:
            raise ValueError(
                f"Unsupported range semantics: {self.semantics!r}. "
                f"Expected {RANGE_SEMANTICS!r}."
            )

    @property
    def length(self) -> int:
        return self.end - self.start + 1

    def contains(self, coordinate: int) -> bool:
        if isinstance(coordinate, bool) or not isinstance(coordinate, int):
            raise TypeError("coordinate must be an integer.")

        return self.start <= coordinate <= self.end

    def to_dict(self) -> dict[str, Any]:
        return {
            "coordinate_system": self.coordinate_system,
            "start": self.start,
            "end": self.end,
            "semantics": self.semantics,
        }

    @classmethod
    def from_dict(
        cls,
        payload: Mapping[str, Any],
    ) -> "CoordinateRange":
        if not isinstance(payload, Mapping):
            raise TypeError("payload must be a mapping.")

        required = {
            "coordinate_system",
            "start",
            "end",
            "semantics",
        }
        missing = required.difference(payload)

        if missing:
            missing_text = ", ".join(sorted(missing))
            raise ValueError(
                f"CoordinateRange payload is missing: {missing_text}."
            )

        return cls(
            coordinate_system=str(payload["coordinate_system"]),
            start=payload["start"],
            end=payload["end"],
            semantics=str(payload["semantics"]),
        )
