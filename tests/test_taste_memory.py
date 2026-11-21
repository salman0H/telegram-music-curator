import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import taste_memory as memory

class MemoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / 'memory.enc'
        self.env = patch.dict(os.environ, {'TASTE_MEMORY_PASSWORD': 'test-password-not-production', 'TASTE_MEMORY_FILE': str(self.path)}, clear=True)
        self.env.start()
    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()
    def test_encrypted_roundtrip_dedup_and_priority(self):
        for source in ('curator_channel', 'vibe_admin', 'vibe_channel'):
            self.assertTrue(memory.record('-1001', 4, 'Private artist', 'Private title', 1735689600, source))
        self.assertNotIn(b'Private', self.path.read_bytes())
        value = memory.read_store(self.path, 'test-password-not-production')
        self.assertEqual(len(value['events']), 1)
        event = value['events']['-1001:4']
        self.assertEqual(event['preference_weight'], 3)
        self.assertEqual(event['time_bucket'], 'night')
        self.assertEqual(event['music_mood']['label'], 'unknown')
        self.assertIsNone(event['self_reported_mood'])
    def test_unmapped_raw_hashtag_retained_only_in_encrypted_memory(self):
        from tag_profile import report_text
        self.assertTrue(memory.record('c', 8, 'Artist', 'Song', None, 'vibe_admin', tags=['#PRIVATE_UNMAPPED_TAG']))
        value=memory.read_store(self.path, os.environ['TASTE_MEMORY_PASSWORD'])
        self.assertEqual(value['events']['c:8']['raw_tag_observations']['vibe_admin'], ['#PRIVATE_UNMAPPED_TAG'])
        self.assertNotIn('PRIVATE_UNMAPPED_TAG', report_text(value))

    def test_wrong_password_and_tampering_preserve_file(self):
        memory.record('c', 1, 'a', 't', None, 'vibe_admin')
        original = self.path.read_bytes()
        with patch.dict(os.environ, {'TASTE_MEMORY_PASSWORD': 'wrong'}):
            self.assertFalse(memory.record('c', 2, 'a', 't', None, 'vibe_admin'))
        self.assertEqual(self.path.read_bytes(), original)
        envelope = json.loads(original)
        envelope['ciphertext'] = envelope['ciphertext'][:-10] + 'AAAAAAAAAA'
        self.path.write_text(json.dumps(envelope))
        damaged = self.path.read_bytes()
        self.assertFalse(memory.record('c', 3, 'a', 't', None, 'vibe_admin'))
        self.assertEqual(self.path.read_bytes(), damaged)
    def test_missing_password_disables_and_unknown_time_stays_unknown(self):
        with patch.dict(os.environ, {'TASTE_MEMORY_PASSWORD': ''}):
            self.assertFalse(memory.record('c', 1, 'a', 't', None, 'vibe_admin'))
        self.assertFalse(self.path.exists())
        memory.record('c', 1, 'a', 't', None, 'vibe_admin')
        event = memory.read_store(self.path, os.environ['TASTE_MEMORY_PASSWORD'])['events']['c:1']
        self.assertIsNone(event['local_time'])
    def test_merge_uses_max_weight_and_chart_unknown_coverage(self):
        memory.record('c', 1, 'a', 't', 1735689600, 'curator_channel')
        first = memory.read_store(self.path, os.environ['TASTE_MEMORY_PASSWORD'])
        memory.record('c', 1, 'a', 't', 1735689600, 'vibe_admin')
        second = memory.read_store(self.path, os.environ['TASTE_MEMORY_PASSWORD'])
        merged = memory.merge([first, second])
        self.assertEqual(merged['events']['c:1']['preference_weight'], 3)
        output = Path(self.tmp.name) / 'chart.svg'
        memory.chart(merged, output)
        self.assertIn('0/1 classified', output.read_text())
        self.assertIn('NOT a measure', output.read_text())
    def test_fuzzy_explanation_survives_authenticated_encryption(self):
        estimate = dict(label='happy', valence=.5, energy=.8, confidence=.9,
                        tags=['upbeat'], basis='test_fixture', model='test')
        with patch.object(memory, 'classify', return_value=estimate):
            self.assertTrue(memory.record('c', 9, 'Artist', 'Song', 1735689600, 'vibe_admin', tags=['happy','energetic']))
        event = memory.read_store(self.path, os.environ['TASTE_MEMORY_PASSWORD'])['events']['c:9']
        self.assertEqual(event['fuzzy_music']['method'], 'mamdani-music-v1')
        self.assertEqual(event['fuzzy_music']['status'], 'estimated')
        self.assertGreater(event['fuzzy_music']['valence_score'], 0)
        self.assertTrue(event['fuzzy_music']['rules'])
        self.assertAlmostEqual(sum(event['time_memberships'].values()), 1)
        self.assertIsNone(event['self_reported_mood'])

    @patch('urllib.request.urlopen')
    def test_invalid_local_model_output_is_unknown(self, request):
        request.return_value.__enter__.return_value.read.return_value = json.dumps({'response': json.dumps({'label':'happy', 'valence': 2, 'energy': 1, 'confidence': 1})}).encode()
        with patch.dict(os.environ, {'TASTE_OLLAMA_MODEL': 'local-model'}):
            self.assertEqual(memory.classify('a','t')['label'], 'unknown')
        request.assert_not_called()

if __name__ == '__main__': unittest.main()
