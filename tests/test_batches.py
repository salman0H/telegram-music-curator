import argparse
import sys
import unittest
from contextlib import ExitStack, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import music_curator as curator


def updates(count):
    return [{'update_id': i, 'channel_post': {
        'message_id': i, 'chat': {'id': -1001},
        'audio': {'performer': 'Artist', 'title': f'Title {i}'}}}
        for i in range(1, count + 1)]


class BatchTests(unittest.TestCase):
    def run_batch(self, count, failed=None):
        posts = updates(count)
        pages = [posts[i:i + 100] for i in range(0, count, 100)] + [[]]
        st = {'offset': None, 'processed_ids': [], 'consecutive_failures': 0}
        index = {}
        with ExitStack() as stack:
            def mock(target, **kwargs):
                return stack.enter_context(patch(target, **kwargs))
            mock('music_curator.parse_args', return_value=argparse.Namespace(dry_run=False))
            mock('music_curator.telegram_client.CHANNEL_ID', new='-1001')
            get = mock('music_curator.telegram_client.get_updates', side_effect=pages)
            mock('music_curator.state.load_state', return_value=st)
            save = mock('music_curator.state.save_state')
            mock('music_curator.hashtag_index.load_index', return_value=index)
            mock('music_curator.hashtag_index.save_index')
            summary = mock('music_curator.hashtag_index.write_summary')
            def process(channel, message_id, audio, dry_run):
                if message_id == failed:
                    return False, None, None, []
                return True, 'Artist', audio['title'], ['#Rock']
            process_mock = mock('music_curator.process_track', side_effect=process)
            send = mock('music_curator.telegram_client.send_message', return_value={
                'ok': True, 'result': {'message_id': 900}})
            pin = mock('music_curator.telegram_client.pin_chat_message')
            stack.enter_context(redirect_stdout(StringIO()))
            curator.main()
        return st, index, process_mock, send, pin, summary, get

    def test_100_tracks_are_all_categorized_and_indexed(self):
        st, index, process, send, pin, summary, get = self.run_batch(100)
        self.assertEqual(process.call_count, 100)
        self.assertEqual(len(index['#Rock']), 100)
        self.assertEqual(len(st['processed_ids']), 100)
        self.assertEqual(st['pending_updates'], [])
        self.assertGreater(send.call_count, 1)
        self.assertEqual(pin.call_count, send.call_count)
        self.assertTrue(summary.called)

    def test_above_100_uses_link_only_path_across_pages(self):
        st, index, process, send, pin, summary, get = self.run_batch(101)
        process.assert_not_called()
        summary.assert_not_called()
        self.assertEqual(index, {})
        self.assertEqual(len(st['processed_ids']), 101)
        self.assertEqual(st['pending_updates'], [])
        self.assertEqual(get.call_args_list[1].kwargs['offset'], 101)
        texts = '\n'.join(call.args[0] for call in send.call_args_list)
        for i in range(1, 102):
            self.assertIn(f"href='https://t.me/c/1/{i}'", texts)
        self.assertEqual(pin.call_count, send.call_count)

    def test_failed_track_remains_queued(self):
        st, index, *_ = self.run_batch(30, failed=15)
        self.assertEqual(len(index['#Rock']), 29)
        self.assertEqual([u['update_id'] for u in st['pending_updates']], [15])

    def test_summaries_keep_every_link_and_valid_html(self):
        items = [(i, '<&>' * 1000) for i in range(100)]
        messages = curator.build_summary_messages(items)
        self.assertGreater(len(messages), 1)
        self.assertTrue(all(len(message) <= 4000 for message in messages))
        joined = '\n'.join(messages)
        self.assertEqual(joined.count('</a>'), 100)
        self.assertNotIn('[Truncated]', joined)
