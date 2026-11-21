import tempfile
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from tag_chart import render_jpg
class JpegTests(unittest.TestCase):
    def test_real_jpeg_header_rgb_and_dimensions(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as tmp:
            output=Path(tmp)/'chart.jpg'
            render_jpg({'events':{}},output)
            self.assertEqual(output.read_bytes()[:3],b'\xff\xd8\xff')
            with Image.open(output) as image:
                self.assertEqual(image.format,'JPEG')
                self.assertEqual(image.mode,'RGB')
                self.assertEqual(image.size,(1600,1060))
            self.assertEqual(output.stat().st_mode & 0o777,0o600)
    def test_tagged_and_unknown_time_inputs_render(self):
        from PIL import Image
        store={'events':{'1':{'sources':['vibe_admin'],'tag_observations':{'vibe_admin':['sad','rock']},'time_bucket':'unknown'},'2':{'sources':['vibe_queue'],'time_bucket':'morning','sent_at_utc':123}}}
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'chart.jpg'
            render_jpg(store,path)
            with Image.open(path) as image:image.verify()
if __name__=='__main__':unittest.main()
