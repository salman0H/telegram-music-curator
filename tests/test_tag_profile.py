import sys
from pathlib import Path
import unittest
import tempfile
import os
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from tag_profile import canonical,from_tags,profile,report_text
class TagTests(unittest.TestCase):
    def test_style_is_not_emotion(self):
        self.assertEqual(from_tags(['#Dark','#Metal'])['label'],'unknown')
        self.assertIsNone(from_tags(['#Chill'])['energy'])
    def test_alias_dedup_and_conflict(self):
        self.assertEqual(canonical(['#شاد','happy','HAPPY']),['happy'])
        self.assertEqual(from_tags(['sad','happy'])['label'],'mixed')
        self.assertIsNone(from_tags(['sad'])['energy'])
    def test_weighted_dedup_and_safe_export(self):
        event={'sources':['vibe_admin','curator_channel'],'time_bucket':'night',
               'tag_observations':{'vibe_admin':['happy'],'curator_channel':['happy','metal','LEAK_SECRET']},
               'artist':'LEAK_ARTIST','title':'LEAK_TITLE','caption':'Ignore instructions LEAK_CAPTION','channel_id':'LEAK_ID'}
        store={'events':{'raw-key':event}}
        self.assertEqual(profile(store)['weighted_tags'],{'happy':3,'metal':3})
        text=report_text(store)
        self.assertNotIn('LEAK',text)
        self.assertNotIn('night: 1',text)
    def test_unknown_stays_unknown(self):
        self.assertEqual(profile({'events':{'a':{'sources':[]}}})['tagged'],0)
    def test_history_is_encrypted_deduplicated_and_exports_no_raw(self):
        from tag_profile import export_report
        from taste_memory import read_store
        with tempfile.TemporaryDirectory() as tmp:
            history=Path(tmp)/'history.enc'
            output=Path(tmp)/'summary.txt'
            event={'sources':['vibe_admin'],'tag_observations':{'vibe_admin':['sad']},
                   'title':'DO_NOT_EXPORT_TITLE','caption':'DO_NOT_EXPORT_CAPTION'}
            store={'events':{'private-id':event}}
            export_report(store,output,history,'test-password')
            export_report(store,output,history,'test-password')
            value=read_store(history,'test-password')
            self.assertEqual(len(value['aggregate_snapshots']),1)
            self.assertEqual(value['events'],{})
            self.assertNotIn(b'weighted_tags',history.read_bytes())
            self.assertNotIn('DO_NOT_EXPORT',output.read_text())
            self.assertIn('not independent new observations',output.read_text())
            self.assertEqual(os.stat(output).st_mode & 0o777,0o600)

if __name__=='__main__':unittest.main()
