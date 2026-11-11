import sys
import io
import urllib.error
from contextlib import redirect_stdout
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
    def test_similar_tracks_include_artist(self, get, resolve):
        get.return_value = {'similartracks': {'track': [
            {'name': 'Original', 'artist': {'name': 'Artist'}}, {'name': 'Next', 'artist': {'name': 'Singer'}}, {'name': ' next ', 'artist': {'name': 'Singer'}},
            {'name': 'Other', 'artist': {'name': 'Singer'}}, {'name': 'Third', 'artist': {'name': 'Band'}}, {'name': 'Fourth'}]}}
        self.assertEqual(rec.recommend_tracks('Artist', 'Original'), ['Singer — Next', 'Singer — Other', 'Band — Third'])
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
        self.assertTrue(caption.endswith('• A &amp; B\n• &lt;Next&gt;'))
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


class ProviderTests(unittest.TestCase):
    @patch.object(rec.time, 'sleep')
    @patch.object(rec.urllib.request, 'urlopen')
    def test_timeout_retries_without_leaking_url(self, open_url, sleep):
        open_url.side_effect = [TimeoutError('secret-key'), io.StringIO('{"ok": true}')]
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(rec._get_json('https://ws.audioscrobbler.com/?api_key=secret-key'), {'ok': True})
        self.assertEqual(open_url.call_count, 2)
        self.assertNotIn('secret-key', output.getvalue())
        self.assertIn('Last.fm: TimeoutError', output.getvalue())

    @patch.object(rec.time, 'sleep')
    @patch.object(rec.urllib.request, 'urlopen')
    def test_rate_limit_respects_retry_after(self, open_url, sleep):
        open_url.side_effect = [urllib.error.HTTPError('hidden', 429, 'limited', {'Retry-After': '7'}, None),
                                io.StringIO('{}')]
        rec._get_json('https://musicbrainz.org/ws/2/recording/')
        self.assertEqual(open_url.call_count, 2)
        sleep.assert_any_call(7)

    @patch.object(rec.time, 'sleep')
    @patch.object(rec.urllib.request, 'urlopen')
    def test_permanent_api_error_is_not_retried(self, open_url, sleep):
        open_url.return_value = io.StringIO('{"error": 10}')
        self.assertEqual(rec._get_json('https://ws.audioscrobbler.com/'), {'error': 10})
        self.assertEqual(open_url.call_count, 1)

    @patch.dict('os.environ', {'LASTFM_API_KEY': 'test'})
    @patch.object(rec, '_resolve_recording', return_value='unknown-mbid')
    @patch.object(rec, '_get_json', side_effect=[{'error': 6}, {'similartracks': {'track': [{'name': 'Next', 'artist': {'name': 'Singer'}}]}}])
    def test_empty_mbid_result_retries_artist_title(self, get, resolve):
        self.assertEqual(rec.recommend_tracks('Artist', 'Original'), ['Singer — Next'])
        url = get.call_args.args[0]
        self.assertNotIn('mbid=', url)
        self.assertIn('artist=Artist', url)

    def test_empty_or_oversized_suggestions_have_no_heading(self):
        for suggestions in ([], ['x' * 1024]):
            caption = caption_formatter.build_caption('Artist', 'Title', recommendations=suggestions)
            self.assertNotIn('🎧', caption)
