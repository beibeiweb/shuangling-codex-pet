import importlib.util
import json
from pathlib import Path
import tempfile
import tomllib
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('installer', ROOT / 'scripts/install.py')
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


class InstallTests(unittest.TestCase):
    def test_shortcut_with_spaces_and_unicode(self):
        with tempfile.TemporaryDirectory(prefix='shuangling-link-') as tmp:
            root = Path(tmp) / '霜铃 files'
            result = installer.shortcut_bytes(root / 'test.lnk', root / 'launcher.exe', root / 'pet.ico')
            self.assertTrue(result.startswith(b'L\x00\x00\x00'))
            self.assertFalse((root / 'test.lnk').exists())

    def test_multiline_notify_and_other_config_preserved(self):
        source = '# comment\nnotify = [\n "old.exe",\n "arg",\n]\nmodel="test"\n[features]\nx=true\n'
        result = installer.replace_notify(source, ['C:\\New Folder\\pythonw.exe', 'notify.py'])
        self.assertEqual(tomllib.loads(result)['features'], {'x': True})
        self.assertEqual(tomllib.loads(result)['model'], 'test')
        self.assertTrue(result.startswith('# comment'))
        self.assertNotIn('notify', tomllib.loads(installer.replace_notify(result, None)))

    def test_roundtrip_and_changed_file_guard(self):
        with tempfile.TemporaryDirectory(prefix='shuangling-test-') as tmp:
            root = Path(tmp)
            config = root / 'codex/config.toml'
            config.parent.mkdir()
            config.write_text('notify=["original.exe","hook"]\nmodel="example"\n[features]\nx=true\n', encoding='utf-8')
            old = tomllib.loads(config.read_text())
            pet = root / 'codex/pets/shuangling-white-dragon/pet.json'
            pet.parent.mkdir(parents=True)
            pet.write_bytes(b'previous pet')
            installer.run('install', tmp)
            settings = json.loads((root / 'app/voice/settings.json').read_text(encoding='utf-8'))
            self.assertEqual(settings['previous_notify'], old['notify'])
            with self.assertRaises(ValueError):
                installer.run('install', tmp)
            pet.write_bytes(b'user edit')
            with self.assertRaises(ValueError):
                installer.run('uninstall', tmp)
            pet.write_bytes((ROOT / 'pet/pet.json').read_bytes())
            # Unrelated edits made after installation must survive uninstall.
            config.write_text(config.read_text(encoding='utf-8') + '\nnew_setting="keep"\n', encoding='utf-8')
            installer.run('uninstall', tmp)
            restored = tomllib.loads(config.read_text(encoding='utf-8'))
            self.assertEqual(restored['notify'], old['notify'])
            self.assertEqual(restored['features']['new_setting'], 'keep')
            self.assertEqual(pet.read_bytes(), b'previous pet')
            self.assertFalse((root / 'app/voice/notify.py').exists())

    def test_empty_config(self):
        with tempfile.TemporaryDirectory(prefix='shuangling-test-') as tmp:
            installer.run('install', tmp)
            installer.run('uninstall', tmp)
            self.assertEqual(tomllib.loads((Path(tmp) / 'codex/config.toml').read_text()), {})

    def test_write_failure_restores_existing_pet_and_config(self):
        with tempfile.TemporaryDirectory(prefix='shuangling-test-') as tmp:
            config = Path(tmp) / 'codex/config.toml'
            config.parent.mkdir()
            config.write_text('model="keep"\n')
            real_write = installer.write
            def fail_config(path, data):
                if path == config:
                    raise OSError('simulated failure')
                real_write(path, data)
            with patch.object(installer, 'write', fail_config):
                with self.assertRaises(OSError):
                    installer.run('install', tmp)
            self.assertEqual(config.read_text(), 'model="keep"\n')
            self.assertFalse((Path(tmp) / 'app/installation.json').exists())
            self.assertFalse((Path(tmp) / 'codex/pets/shuangling-white-dragon/pet.json').exists())


if __name__ == '__main__':
    unittest.main()
