"""
PrimeNet Entropy Rate Observatory Metadata
"""

OBSERVATORY_ID = "OBS-ENTROPY-RATE"

NAME = "Entropy Rate Observatory"

VERSION = "1.0.0"

CATEGORY = "transition"

AUTHOR = "PrimeNet"

DESCRIPTION = (
    "Observatory for entropy-rate analysis of prime-gap transition dynamics "
    "using transition matrices and stationary distributions."
)

OBSERVATORY_CLASS = "EntropyRateObservatory"

SUPPORTED_INSTRUMENTS = [
    "EntropyRateInstrument",
]

SUPPORTED_PRODUCTS = [
    "entropy_rate_summary.json",
    "entropy_rate_state_contributions.csv",
    "entropy_rate_transition_contributions.csv",
    "entropy_rate_report.md",
]