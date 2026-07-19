from __future__ import annotations
import unittest
from observatories.framework import CoordinateRange, Observation
from observatories.geometry import build_geometry_observation

class GeometryObservationBuilderTests(unittest.TestCase):
    def summary(self):
        return {
            'start':1,'end':1000,'active_state_count':3,'cluster_count':2,
            'geometry_metrics':{'mean_pairwise_distance':0.2,'max_pairwise_distance':0.4,'mean_nearest_neighbor_distance':0.1,'effective_dimension':1.7,'explained_variance_2d':0.9,'explained_variance_3d':1.0},
            'validation':{'status':'PASS'},
            'inputs':{'information_summary_json':'information_summary.json','transition_counts_csv':'transition_counts.csv'},
            'outputs':{'summary_json':'geometry_summary.json'},
        }
    def test_builds_observation(self):
        o=build_geometry_observation(observation_id='G-1',coordinate_range=CoordinateRange(coordinate_system='prime_index',start=1,end=1000),summary=self.summary(),created_utc='2026-07-18T00:00:00Z')
        self.assertIsInstance(o,Observation); self.assertEqual(o.observatory_name,'Geometry Observatory'); self.assertEqual(o.measurements['active_state_count'],3)
    def test_rejects_failed_validation(self):
        s=self.summary(); s['validation']['status']='FAIL'
        with self.assertRaises(ValueError): build_geometry_observation(observation_id='G-2',coordinate_range=CoordinateRange(coordinate_system='prime_index',start=1,end=1000),summary=s)

if __name__=='__main__': unittest.main()
