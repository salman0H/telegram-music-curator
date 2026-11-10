import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import recommendations as rec
import caption_formatter
import music_curator


class RecommendationsTests(unittest.TestCase):
    @patch.dict('os.environ', {'LASTFM_API_KEY': 'test'})
    @patch.object(rec, '_resolve_recording', return_value='recording-id')
    @patch.object(rec, '_get_json')
    def test_similar_titles_only(self, get, resolve):
        get.return_value = {'similartracks': {'track': [
            {'name': 'Original'}, {'name': 'Next'}, {'name': ' next '},
            {'name': 'Other'}, {'name': 'Third'}, {'name': 'Fourth'}]}}
        self.assertEqual(rec.recommend_tracks('Artist', 'Original'), ['Next', 'Other', 'Third'])
        self.assertIn('mbid=recording-id', get.call_args.args[0])

    @patch.dict('os.environ', {}, clear=True)
    @patch.object(rec, '_get_json')
    def test_no_key_skips_network(self, get):
        self.assertEqual(rec.recommend_tracks('Artist', 'Title'), [])
        get.assert_not_called()

    @patch.dict('os.environ', {'LASTFM_API_KEY': 'test'})
    @patch.object(rec, '_resolve_recording', return_value=None)
    @patch.object(rec, '_get_json', return_value={'error': 6})
    def test_missing_recording_falls_back(self, get, resolve):
        self.assertEqual(rec.recommend_tracks('Artist', 'Title'), [])
        self.assertIn('artist=Artist', get.call_args.args[0])
        self.assertIn('track=Title', get.call_args.args[0])

    @patch.object(rec.time, 'sleep')
    @patch.object(rec, '_get_json', return_value={'recordings': [
        {'id': 'wrong', 'title': 'Title', 'artist-credit': [{'artist': {'name': 'Other'}}]},
        {'id': 'right', 'title': 'Title', 'artist-credit': [{'artist': {'name': 'Artist'}}]}]})
    def test_musicbrainz_requires_matching_artist(self, get, sleep):
        self.assertEqual(rec._resolve_recording('Artist', 'Title'), 'right')

    def test_caption_escapes_and_limits_suggestions(self):
        caption = caption_formatter.build_caption('Artist', 'Title', recommendations=['A & B', '<Next>'])
        self.assertTrue(caption.endswith('A &amp; B\n\n&lt;Next&gt;'))
        caption = caption_formatter.build_caption('Artist', 'Title', recommendations=['x' * 1024])
        self.assertLessEqual(len(caption), 1024)

    @patch.object(music_curator.itunes_client, 'search_track', return_value=None)
    @patch.object(music_curator.recommendations, 'recommend_tracks', return_value=['Next Song'])
    @patch.object(music_curator.telegram_client, 'edit_message_caption', return_value={'ok': False})
    @patch.object(music_curator.telegram_client, 'send_message', return_value={'ok': True})
    def test_recommendation_stays_in_analysis_reply(self, send, edit, recommend, search):
        result = music_curator.process_track('-1001', 12, {'performer': 'Artist', 'title': 'Title'}, False)
        self.assertTrue(result[0])
        self.assertEqual(send.call_args.kwargs['reply_to_message_id'], 12)
        self.assertEqual(send.call_args.args[0], edit.call_args.args[1])
        self.assertTrue(send.call_args.args[0].endswith('Next Song'))
