"""
PrimeNet Mission

Mission orchestration layer for running multiple observatories
under one shared PrimeNetSession.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
import time

from core.session import PrimeNetSession
from core.observatory_factory import (
    ObservatoryFactory,
    register_builtin_observatories,
)


@dataclass
class MissionResult:
    mission_name: str
    status: str
    started_at: str
    finished_at: str
    runtime_sec: float
    observatories: dict[str, Any] = field(default_factory=dict)
    notes: str = ""


class PrimeNetMission:
    """
    PrimeNet mission controller.

    A mission runs one or more observatories using one shared session.
    """

    def __init__(
        self,
        mission_name: str = "PrimeNet Mission",
        session: PrimeNetSession | None = None,
    ) -> None:
        register_builtin_observatories()

        self.mission_name = mission_name
        self.session = session or PrimeNetSession(session_name=mission_name)
        self._owns_session = session is None

        self.observatory_keys: list[str] = []
        self.results: dict[str, Any] = {}

        self.started_at: str | None = None
        self.finished_at: str | None = None
        self.runtime_sec: float | None = None
        self.notes: str = ""

    def now(self) -> str:
        return datetime.now().isoformat(timespec="seconds")

    def add(self, key: str) -> None:
        """
        Add one observatory to this mission.
        """
        key = key.strip().lower()

        if key not in ObservatoryFactory.available():
            available = ", ".join(ObservatoryFactory.available())
            raise KeyError(
                f"Unknown observatory: {key}. Available: {available}"
            )

        self.observatory_keys.append(key)

    def add_many(self, keys: list[str]) -> None:
        """
        Add multiple observatories.
        """
        for key in keys:
            self.add(key)

    def run(self) -> MissionResult:
        """
        Run all observatories in this mission.
        """
        self.started_at = self.now()
        t0 = time.time()

        self.session.logger.banner(f"Mission Started: {self.mission_name}")

        try:
            if not self.observatory_keys:
                self.session.logger.info(
                    "No observatories selected. Nothing to run."
                )

            for key in self.observatory_keys:
                self.session.logger.section(f"Run Observatory: {key}")
                result = ObservatoryFactory.run(
                    key=key,
                    session=self.session,
                )
                self.results[key] = result

            self.finished_at = self.now()
            self.runtime_sec = time.time() - t0

            self.session.logger.banner(
                f"Mission Completed: {self.mission_name}"
            )

            mission_result = MissionResult(
                mission_name=self.mission_name,
                status="completed",
                started_at=self.started_at,
                finished_at=self.finished_at,
                runtime_sec=self.runtime_sec,
                observatories=self.results,
                notes=self.notes,
            )

            if self._owns_session:
                self.session.close()

            return mission_result

        except Exception as exc:
            self.finished_at = self.now()
            self.runtime_sec = time.time() - t0
            self.session.logger.error(
                f"Mission failed: {self.mission_name}: {exc}"
            )

            if self._owns_session:
                self.session.close()

            raise

    def summary(self) -> None:
        """
        Print mission summary.
        """
        print("=" * 80)
        print("PrimeNet Mission")
        print("=" * 80)
        print(f"Mission name : {self.mission_name}")
        print(f"Selected observatories: {len(self.observatory_keys)}")
        for key in self.observatory_keys:
            print(f"  - {key}")
        print("=" * 80)


def main() -> None:
    mission = PrimeNetMission("PrimeNet v1.4 Mission Test")
    mission.add("transition")

    mission.summary()
    result = mission.run()

    print()
    print("PrimeNet Mission completed successfully.")
    print(f"Status: {result.status}")
    print(f"Runtime: {result.runtime_sec:.3f} sec")
    print("Observatory results:")
    for key in result.observatories:
        print(f"  - {key}")


if __name__ == "__main__":
    main()