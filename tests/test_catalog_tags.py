import io,json,sys,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from catalog_tags import lookup,genres_to_tags
from backfill_taste_tags import enrich,seed_index
class CatalogTests(unittest.TestCase):
    @patch('catalog_tags.urllib.request.urlopen')
    def test_wrong_first_result_rejected_exact_second_selected(self,request):
        request.return_value=io.StringIO(json.dumps({'results':[
            {'artistName':'Other','trackName':'Song','primaryGenreName':'Pop'},
            {'artistName':'Artist','trackName':'Song','primaryGenreName':'Hip-Hop/Rap','trackId':1}]}))
        result=lookup('Artist','Song')
        self.assertEqual(result['tags'],['hiphop','rap'])
    @patch('catalog_tags.urllib.request.urlopen')
    def test_unmatched_and_unknown_do_not_invent_tags(self,request):
        self.assertEqual(lookup('Unknown Artist','Song')['tags'],[])
        request.assert_not_called()
        request.return_value=io.StringIO('{"results":[{"artistName":"Wrong","trackName":"Song","primaryGenreName":"Pop"}]}')
        self.assertEqual(lookup('Artist','Song')['tags'],[])
    def test_common_genres_are_descriptive_only(self):
        self.assertEqual(genres_to_tags(['R&B/Soul']),['rnb','soul'])
        self.assertEqual(genres_to_tags(['Dance','Singer/Songwriter']),['dance','singersongwriter'])
    @patch('backfill_taste_tags.catalog_tags.lookup',return_value={'status':'matched','tags':['rock'],'provider':'itunes'})
    def test_enrichment_keeps_admin_weight_and_is_idempotent(self,lookup):
        event={'sources':['vibe_admin'],'artist':'Artist','title':'Song','local_time':None}
        store={'events':{'c:1':event}}
        enrich(store,delay=0)
        enrich(store,delay=0)
        lookup.assert_called_once()
        self.assertEqual(event['tag_observations']['catalog_genre'],['rock'])
        self.assertEqual(event['preference_weight'],3)
        self.assertEqual(event['music_mood']['label'],'unknown')
    def test_archive_seed_deduplicates_tags_without_faking_time(self):
        store={'events':{}}
        entry={'message_id':1,'performer':'Artist','title':'Song'}
        self.assertEqual(seed_index(store,{'#Rock':[entry],'#Dark':[entry]},'c'),1)
        enrich(store,limit=0)
        event=store['events']['c:1']
        self.assertEqual(event['tag_observations']['archive_genre'],['dark','rock'])
        self.assertIsNone(event['sent_at_utc'])
if __name__=='__main__':unittest.main()
