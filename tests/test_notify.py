import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('notifier', ROOT / 'voice/notify.py')
notifier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(notifier)


class NotifyTests(unittest.TestCase):
    def test_completion_deduplication_and_original_hook_forwarding(self):
        with tempfile.TemporaryDirectory(prefix='shuangling-notify-') as tmp:
            base = Path(tmp)
            settings = json.loads((ROOT / 'voice/settings.json').read_text())
            settings['previous_notify'] = ['original.exe', 'turn-ended']
            (base / 'settings.json').write_text(json.dumps(settings))
            event = json.dumps({'type': 'agent-turn-complete', 'thread-id': 'thread', 'turn-id': 'turn'})
            with patch.object(notifier, 'ROOT', base), patch.object(notifier.sys, 'argv', ['notify.py', event]), \
                    patch.object(notifier.subprocess, 'Popen') as forward, patch.object(notifier.winsound, 'PlaySound') as sound:
                notifier.main()
                notifier.main()
                self.assertEqual(sound.call_count, 1)
                self.assertEqual(forward.call_count, 2)
                self.assertEqual(forward.call_args.args[0], ['original.exe', 'turn-ended', event])
            self.assertNotIn('thread', (base / 'playback.log').read_text())

    def test_other_events_do_not_play(self):
        with tempfile.TemporaryDirectory(prefix='shuangling-event-') as tmp:
            base = Path(tmp)
            (base / 'settings.json').write_bytes((ROOT / 'voice/settings.json').read_bytes())
            with patch.object(notifier, 'ROOT', base), patch.object(notifier.sys, 'argv', ['notify.py', '{"type":"other"}']), \
                    patch.object(notifier.winsound, 'PlaySound') as sound:
                notifier.main()
                sound.assert_not_called()
