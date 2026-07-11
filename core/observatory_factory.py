"""
PrimeNet Observatory Factory

Central factory for creating PrimeNet observatory instances.

The factory gives PrimeNet one standard way to create observatories:

    obs = ObservatoryFactory.create("transition")
    result = obs.run()
"""

from __future__ import annotations

from typing import Any, Type

from core.observatory import PrimeNetObservatory


class ObservatoryFactory:
    """
    Factory for constructing PrimeNet observatories.
    """

    _registry: dict[str, Type[PrimeNetObservatory]] = {}

    @classmethod
    def register(
        cls,
        key: str,
        observatory_class: Type[PrimeNetObservatory],
    ) -> None:
        """
        Register an observatory class with a short key.
        """
        key = key.strip().lower()

        if not key:
            raise ValueError("Factory key cannot be empty.")

        if not issubclass(observatory_class, PrimeNetObservatory):
            raise TypeError(
                "observatory_class must inherit from PrimeNetObservatory."
            )

        cls._registry[key] = observatory_class

    @classmethod
    def available(cls) -> list[str]:
        """
        Return available factory keys.
        """
        return sorted(cls._registry.keys())

    @classmethod
    def create(
        cls,
        key: str,
        session=None,
        **kwargs: Any,
    ) -> PrimeNetObservatory:
        """
        Create an observatory instance by key.
        """
        key = key.strip().lower()

        if key not in cls._registry:
            available = ", ".join(cls.available()) or "(none)"
            raise KeyError(
                f"Unknown observatory key: {key}. Available: {available}"
            )

        observatory_class = cls._registry[key]
        return observatory_class(session=session, **kwargs)

    @classmethod
    def run(
        cls,
        key: str,
        session=None,
        **kwargs: Any,
    ) -> Any:
        """
        Create and run one observatory.
        """
        obs = cls.create(key=key, session=session, **kwargs)
        return obs.run()

    @classmethod
    def run_all(
        cls,
        session=None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Run all registered observatories.
        """
        results: dict[str, Any] = {}

        for key in cls.available():
            obs = cls.create(key=key, session=session, **kwargs)
            results[key] = obs.run()

        return results


def register_builtin_observatories() -> None:
    """
    Register built-in PrimeNet observatories.

    For now, we register only PNT.
    More observatories will be added here later.
    """
    from observatories.pnt_observatory import PNTObservatory

    ObservatoryFactory.register("transition", PNTObservatory)
    ObservatoryFactory.register("pnt", PNTObservatory)


def main() -> None:
    register_builtin_observatories()

    print("PrimeNet ObservatoryFactory loaded successfully.")
    print("Available observatories:")

    for key in ObservatoryFactory.available():
        print(f"  - {key}")


if __name__ == "__main__":
    main()