"""
PrimeNet Observatory
Entropy Rate Instrument
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Dict

import pandas as pd


class EntropyRateInstrument:
    """
    Computes entropy rate from:

    1. transition matrix P(i -> j)
    2. stationary distribution pi(i)

    H = - sum_i pi_i sum_j P_ij log2(P_ij)
    """

    name = "EntropyRateInstrument"
    version = "1.0.0"

    def __init__(
        self,
        transition_matrix_path: str | Path,
        stationary_distribution_path: str | Path,
        output_dir: str | Path,
    ) -> None:
        self.transition_matrix_path = Path(transition_matrix_path)
        self.stationary_distribution_path = Path(stationary_distribution_path)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _normalize_state(self, value: Any) -> str:
        """
        Normalize state labels.

        Examples:
            6      -> "6"
            6.0    -> "6"
            "6.0"  -> "6"
            "6"    -> "6"
        """
        try:
            f = float(value)
            if f.is_integer():
                return str(int(f))
            return str(f)
        except Exception:
            return str(value).strip()

    def _find_stationary_column(self, df: pd.DataFrame) -> str:
        candidates = [
            "stationary_probability",
            "probability",
            "pi",
            "stationary",
            "mass",
        ]

        lower_map = {c.lower(): c for c in df.columns}

        for c in candidates:
            if c in lower_map:
                return lower_map[c]

        if len(df.columns) < 2:
            raise ValueError(
                "Stationary distribution file must contain at least two columns."
            )

        return df.columns[1]

    def run(self) -> Dict[str, Any]:
        transition_df = pd.read_csv(self.transition_matrix_path)
        stationary_df = pd.read_csv(self.stationary_distribution_path)

        source_col = transition_df.columns[0]
        state_col = stationary_df.columns[0]
        stationary_col = self._find_stationary_column(stationary_df)

        pi = {
            self._normalize_state(row[state_col]): float(row[stationary_col])
            for _, row in stationary_df.iterrows()
        }

        state_rows = []
        transition_rows = []

        entropy_rate = 0.0
        total_stationary_mass_used = 0.0
        matched_states = 0
        unmatched_states = 0

        for _, row in transition_df.iterrows():
            source = self._normalize_state(row[source_col])
            pi_i = pi.get(source, 0.0)

            if pi_i > 0:
                matched_states += 1
                total_stationary_mass_used += pi_i
            else:
                unmatched_states += 1

            conditional_entropy = 0.0

            for target in transition_df.columns[1:]:
                p_ij = float(row[target])

                if p_ij <= 0.0:
                    continue

                information_bits = -math.log2(p_ij)
                weighted_information = pi_i * p_ij * information_bits

                conditional_entropy += p_ij * information_bits
                entropy_rate += weighted_information

                transition_rows.append(
                    {
                        "source_state": source,
                        "target_state": self._normalize_state(target),
                        "transition_probability": p_ij,
                        "information_bits": information_bits,
                        "stationary_probability": pi_i,
                        "weighted_information": weighted_information,
                    }
                )

            state_rows.append(
                {
                    "state": source,
                    "stationary_probability": pi_i,
                    "conditional_entropy_bits": conditional_entropy,
                    "entropy_rate_contribution": pi_i * conditional_entropy,
                }
            )

        state_df = pd.DataFrame(state_rows)
        transition_contrib_df = pd.DataFrame(transition_rows)

        max_contribution_state = None
        max_contribution_value = None

        if not state_df.empty:
            max_row = state_df.sort_values(
                "entropy_rate_contribution", ascending=False
            ).iloc[0]
            max_contribution_state = str(max_row["state"])
            max_contribution_value = float(max_row["entropy_rate_contribution"])

        summary = {
            "instrument": self.name,
            "version": self.version,
            "transition_matrix_path": str(self.transition_matrix_path),
            "stationary_distribution_path": str(self.stationary_distribution_path),
            "num_states": int(len(state_df)),
            "num_transitions_nonzero": int(len(transition_contrib_df)),
            "matched_states": int(matched_states),
            "unmatched_states": int(unmatched_states),
            "total_stationary_mass_used": float(total_stationary_mass_used),
            "entropy_rate_bits_per_step": float(entropy_rate),
            "max_contribution_state": max_contribution_state,
            "max_contribution_value": max_contribution_value,
        }

        self._write_outputs(summary, state_df, transition_contrib_df)
        return summary

    def _write_outputs(
        self,
        summary: Dict[str, Any],
        state_df: pd.DataFrame,
        transition_contrib_df: pd.DataFrame,
    ) -> None:
        summary_path = self.output_dir / "entropy_rate_summary.json"
        state_path = self.output_dir / "entropy_rate_state_contributions.csv"
        transition_path = self.output_dir / "entropy_rate_transition_contributions.csv"
        report_path = self.output_dir / "entropy_rate_report.md"

        with summary_path.open("w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)

        state_df.to_csv(state_path, index=False)
        transition_contrib_df.to_csv(transition_path, index=False)

        with report_path.open("w", encoding="utf-8") as f:
            f.write("# PrimeNet Entropy Rate Report\n\n")
            f.write(f"Instrument: `{self.name}`\n\n")
            f.write(f"Version: `{self.version}`\n\n")
            f.write(
                f"Entropy rate: **{summary['entropy_rate_bits_per_step']:.12f} "
                "bits/step**\n\n"
            )
            f.write(f"Number of states: {summary['num_states']}\n\n")
            f.write(
                f"Nonzero transitions: {summary['num_transitions_nonzero']}\n\n"
            )
            f.write(f"Matched states: {summary['matched_states']}\n\n")
            f.write(f"Unmatched states: {summary['unmatched_states']}\n\n")
            f.write(
                f"Stationary mass used: "
                f"{summary['total_stationary_mass_used']:.12f}\n\n"
            )
            f.write(
                f"Max contribution state: "
                f"{summary['max_contribution_state']}\n\n"
            )
            f.write(
                f"Max contribution value: "
                f"{summary['max_contribution_value']:.12f}\n\n"
            )

        print(f"Wrote summary: {summary_path}")
        print(f"Wrote state contributions: {state_path}")
        print(f"Wrote transition contributions: {transition_path}")
        print(f"Wrote report: {report_path}")


def main() -> None:
    transition_matrix_path = (
        "products/results/transition/inst-transition-matrix/"
        "transition_matrix.csv"
    )

    stationary_distribution_path = (
        "products/results/transition/inst-stationary-distribution/"
        "stationary_distribution.csv"
    )

    output_dir = "products/results/entropy_rate/inst-entropy-rate"

    instrument = EntropyRateInstrument(
        transition_matrix_path=transition_matrix_path,
        stationary_distribution_path=stationary_distribution_path,
        output_dir=output_dir,
    )

    summary = instrument.run()

    print("\nEntropy Rate Instrument completed successfully.")
    print(f"Entropy rate: {summary['entropy_rate_bits_per_step']:.12f} bits/step")
    print(f"States: {summary['num_states']}")
    print(f"Nonzero transitions: {summary['num_transitions_nonzero']}")
    print(f"Matched states: {summary['matched_states']}")
    print(f"Unmatched states: {summary['unmatched_states']}")
    print(f"Max contribution state: {summary['max_contribution_state']}")
    print("\nFull summary:")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()