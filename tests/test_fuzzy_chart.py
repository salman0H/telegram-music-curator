import unittest,sys,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from fuzzy_chart import fuzzy_profile,render_jpg
class FuzzyChartTests(unittest.TestCase):
    def test_real_time_membership_without_invented_affect(self):
        event={'local_time':'2026-11-21T00:00:00+03:30','preference_weight':3,'music_mood':{'label':'unknown'}}
        result=fuzzy_profile({'events':{'a':event}})
        self.assertEqual(result['weighted_time_membership']['night'],.5)
        self.assertEqual(result['weighted_time_membership']['evening'],.5)
        self.assertEqual(result['affect_points'],[])
        self.assertEqual(result['affect']['classified'],0)
    def test_jpeg_no_data_and_no_raw_metadata(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'fuzzy.jpg'
            render_jpg({'events':{}},path)
            with Image.open(path) as image:
                self.assertEqual(image.format,'JPEG')
                self.assertEqual(image.size,(1600,1100))
if __name__=='__main__':unittest.main()
