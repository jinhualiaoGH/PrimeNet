from __future__ import annotations
import unittest
import numpy as np
from observatories.geometry.engine import compute_geometry_metrics, validate_transition_counts

class GeometryEngineTests(unittest.TestCase):
    def test_identical_profiles_have_zero_distance(self):
        counts=np.array([[1,1],[2,2]],dtype=np.int64)
        m=compute_geometry_metrics(counts,cluster_count=1,neighbor_count=1)
        self.assertAlmostEqual(float(m.combined_distance[0,1]),0.0,places=12)

    def test_deterministic_profiles_are_separated(self):
        counts=np.array([[10,0],[0,10]],dtype=np.int64)
        m=compute_geometry_metrics(counts,cluster_count=2,neighbor_count=1)
        self.assertGreater(float(m.combined_distance[0,1]),0.9)
        self.assertTrue(np.all(np.isfinite(m.embedding_3d)))

    def test_distance_contract(self):
        counts=np.array([[5,2,1],[1,4,2],[2,1,6]],dtype=np.int64)
        m=compute_geometry_metrics(counts,cluster_count=2,neighbor_count=2)
        self.assertTrue(np.allclose(m.combined_distance,m.combined_distance.T))
        self.assertTrue(np.allclose(np.diag(m.combined_distance),0.0))
        self.assertEqual(m.active_state_count,3)
        self.assertEqual(len(m.cluster_assignments),3)

    def test_inactive_states_removed(self):
        counts=np.array([[2,1,0],[0,0,0],[1,2,0]],dtype=np.int64)
        m=compute_geometry_metrics(counts,state_labels=['a','b','c'],cluster_count=2)
        self.assertEqual(m.active_labels,('a','c'))

    def test_invalid_matrix_rejected(self):
        with self.assertRaises(ValueError): validate_transition_counts(np.array([[1,2,3]]))
        with self.assertRaises(ValueError): validate_transition_counts(np.array([[1,-1], [0,1]]))

if __name__=='__main__': unittest.main()
