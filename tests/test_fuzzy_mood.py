import math
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from fuzzy_mood import partition, centroid, infer, time_memberships, summarize
from evaluate_mood import evaluate

def mood(v=0,e=.5,c=1):
    return dict(label='estimated', valence=v, energy=e, confidence=c)

class FuzzyTests(unittest.TestCase):
    def test_partition_covers_domain(self):
        for i in range(201):
            degrees=partition(-1+i/100)
            self.assertAlmostEqual(sum(degrees.values()),1)
            self.assertTrue(all(0<=x<=1 for x in degrees.values()))
    def test_centroid_matches_analytic_shoulders(self):
        self.assertAlmostEqual(centroid({'negative':1}),-2/3,places=4)
        self.assertAlmostEqual(centroid({'positive':1}),2/3,places=4)
        self.assertAlmostEqual(centroid({'neutral':1}),0,places=10)
        self.assertIsNone(centroid({}))
    def test_mamdani_symmetry_and_monotonicity(self):
        values=[infer(mood(i/20))['valence_score'] for i in range(-20,21)]
        self.assertTrue(all(a<=b+1e-12 for a,b in zip(values,values[1:])))
        for a,b in zip(values,reversed(values)): self.assertAlmostEqual(a,-b)
    def test_rules_explain_overlap(self):
        result=infer(mood(.5,.75))
        self.assertEqual(len(result['rules']),4)
        self.assertEqual(result['memberships']['happy_energetic'],.5)
        self.assertFalse(result['membership_is_probability'])
    def test_invalid_or_missing_evidence_abstains(self):
        for value in [None,float('nan'),float('inf'),True,2]:
            self.assertEqual(infer(mood(value))['status'],'unknown')
        self.assertEqual(infer(mood(c=.69))['status'],'unknown')
        self.assertEqual(infer({'label':'unknown'})['status'],'unknown')
    def test_time_is_circular_and_smooth(self):
        midnight=time_memberships('2026-11-17T00:00:00+03:30')
        self.assertEqual(midnight['night'],.5)
        self.assertEqual(midnight['evening'],.5)
        for hour in range(24):
            self.assertAlmostEqual(sum(time_memberships(f'2026-11-17T{hour:02}:00:00+03:30').values()),1)
        self.assertEqual(time_memberships(None),{})
    def test_summary_priority_coverage_and_kish(self):
        rows=[dict(preference_weight=3,music_mood=mood(1)),dict(preference_weight=1,music_mood=mood(-1)),dict(preference_weight=1,music_mood={})]
        result=summarize(rows)
        self.assertAlmostEqual(result['valence'],1/3,places=4)
        self.assertAlmostEqual(result['effective_sample_size'],1.6)
        self.assertEqual(result['classified'],2)
        self.assertAlmostEqual(result['coverage'],2/3)
        self.assertFalse(result['statistically_validated'])
    def test_evaluation_compares_against_raw_baseline(self):
        result=evaluate([dict(model_valence=1,human_valence=1,energy=.5,confidence=1)])
        self.assertEqual(result['raw_mae'],0)
        self.assertGreater(result['fuzzy_mae'],0)
        self.assertIsNone(evaluate([])['fuzzy_mae'])

if __name__=='__main__':unittest.main()
