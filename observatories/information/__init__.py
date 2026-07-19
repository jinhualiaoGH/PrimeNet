from .engine import (
    InformationMetrics,
    compute_information_metrics,
    read_transition_counts_csv,
    validate_transition_counts,
)

_BUILDER_EXPORTS = {
    "build_entropy_information_observation",
    "build_geometry_information_observation",
    "build_information_observation",
    "build_invariant_information_observation",
    "build_taxonomy_information_observation",
    "build_transition_information_observation",
    "build_transition_metrics_information_observation",
}


def __getattr__(name: str):
    if name in _BUILDER_EXPORTS:
        from . import observation_builder
        return getattr(observation_builder, name)
    raise AttributeError(name)


__all__ = [
    "InformationMetrics",
    "compute_information_metrics",
    "read_transition_counts_csv",
    "validate_transition_counts",
    *_BUILDER_EXPORTS,
]
