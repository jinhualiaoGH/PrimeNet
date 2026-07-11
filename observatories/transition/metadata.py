"""
PrimeNet Transition Observatory Metadata
"""

OBSERVATORY_ID = "OBS-TRANSITION"

NAME = "Transition Observatory"

VERSION = "1.0.0"

CATEGORY = "transition"

AUTHOR = "PrimeNet"

DESCRIPTION = (
    "Observatory for transition-based analysis of prime gap dynamics, "
    "including transition matrices, stationary distributions, entropy "
    "rate, spectral properties, mixing time, and related observables."
)

SUPPORTED_INSTRUMENTS = [
    "TransitionMatrixInstrument",
    "StationaryDistributionInstrument",
    "EntropyRateInstrument",
    "SpectralGapInstrument",
    "MixingTimeInstrument",
]