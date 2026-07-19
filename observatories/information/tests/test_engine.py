from __future__ import annotations

import csv
from pathlib import Path
import tempfile
import unittest

import numpy as np

from observatories.information.engine import (
    compute_information_metrics,
    read_transition_counts_csv,
    validate_transition_counts,
)


class InformationEngineTests(unittest.TestCase):
    def test_deterministic_chain_has_zero_entropy_rate(self) -> None:
        result = compute_information_metrics(np.array([[10, 0], [0, 10]]))
        self.assertAlmostEqual(result.entropy_rate_bits, 0.0)
        self.assertAlmostEqual(result.mutual_information_bits, 1.0)
        self.assertAlmostEqual(result.predictability_fraction, 1.0)

    def test_uniform_independent_chain(self) -> None:
        result = compute_information_metrics(np.ones((2, 2), dtype=np.int64))
        self.assertAlmostEqual(result.source_entropy_bits, 1.0)
        self.assertAlmostEqual(result.target_entropy_bits, 1.0)
        self.assertAlmostEqual(result.conditional_entropy_bits, 1.0)
        self.assertAlmostEqual(result.mutual_information_bits, 0.0)
        self.assertAlmostEqual(result.effective_target_alphabet, 2.0)

    def test_asymmetric_chain_obeys_information_identities(self) -> None:
        result = compute_information_metrics(np.array([[30, 10], [5, 55]]))
        self.assertAlmostEqual(result.joint_entropy_bits, result.source_entropy_bits + result.conditional_entropy_bits)
        self.assertAlmostEqual(result.mutual_information_bits, result.target_entropy_bits - result.conditional_entropy_bits)
        self.assertAlmostEqual(float(result.joint_distribution.sum()), 1.0)

    def test_labels_are_preserved(self) -> None:
        result = compute_information_metrics(np.eye(2, dtype=np.int64), state_labels=["2", "4"])
        self.assertEqual(result.state_labels, ("2", "4"))

    def test_non_square_matrix_rejected(self) -> None:
        with self.assertRaises(ValueError):
            validate_transition_counts(np.ones((2, 3)))

    def test_negative_matrix_rejected(self) -> None:
        with self.assertRaises(ValueError):
            validate_transition_counts(np.array([[1, -1], [0, 1]]))

    def test_nan_matrix_rejected(self) -> None:
        with self.assertRaises(ValueError):
            validate_transition_counts(np.array([[1.0, np.nan], [0.0, 1.0]]))

    def test_fractional_counts_rejected(self) -> None:
        with self.assertRaises(ValueError):
            validate_transition_counts(np.array([[0.5, 0.5], [1.0, 1.0]]))

    def test_zero_mass_rejected(self) -> None:
        with self.assertRaises(ValueError):
            validate_transition_counts(np.zeros((2, 2)))

    def test_duplicate_labels_rejected(self) -> None:
        with self.assertRaises(ValueError):
            compute_information_metrics(np.eye(2), state_labels=["x", "x"])

    def test_csv_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "counts.csv"
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle)
                writer.writerow(["source_state", "2", "4"])
                writer.writerow(["2", 3, 1])
                writer.writerow(["4", 2, 4])
            labels, matrix = read_transition_counts_csv(path)
            self.assertEqual(labels, ("2", "4"))
            np.testing.assert_array_equal(matrix, np.array([[3.0, 1.0], [2.0, 4.0]]))

    def test_csv_label_mismatch_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "counts.csv"
            path.write_text("source_state,2,4\n4,1,0\n2,0,1\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                read_transition_counts_csv(path)


if __name__ == "__main__":
    unittest.main()
