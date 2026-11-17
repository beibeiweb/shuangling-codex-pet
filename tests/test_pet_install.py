"""Exercise the Python-free pet installer against isolated Windows directories."""
import ctypes
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts/install-pet.ps1'
NAMES = ['spritesheet.webp', 'pet.json']


class PetInstallTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='shuangling-pet-install-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.package = self.root / 'package'
        (self.package / 'pet').mkdir(parents=True)
        for name in NAMES:
            (self.package / 'pet' / name).write_bytes((ROOT / 'pet' / name).read_bytes())
        self.refresh_manifest()
        self.codex, self.state = self.root / 'codex', self.root / 'state'
        self.pet = self.codex / 'pets/shuangling-white-dragon'
        self.pet.mkdir(parents=True)
        self.old = {'pet.json': b'previous metadata', 'spritesheet.webp': b'previous atlas'}
        for name, data in self.old.items():
            (self.pet / name).write_bytes(data)
        self.config = self.codex / 'config.toml'
        self.config.write_bytes(b'# unchanged\nmodel="example"\n')

    def refresh_manifest(self):
        files = {name: hashlib.sha256((self.package / 'pet' / name).read_bytes()).hexdigest() for name in NAMES}
        (self.package / 'pet/package-manifest.json').write_text(json.dumps({'schema': 1, 'files': files}), encoding='utf-8')

    def run_installer(self, action='Install', ok=True):
        result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass',
                                 '-File', str(SCRIPT), '-Action', action, '-PackageRoot', str(self.package),
                                 '-CodexHome', str(self.codex), '-StateHome', str(self.state)],
                                capture_output=True, text=True, encoding='utf-8', errors='replace')
        if ok:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0)
        return result

    def test_pet_only_roundtrip_preserves_configuration_and_user_files(self):
        self.run_installer()
        for name in NAMES:
            self.assertEqual((self.pet / name).read_bytes(), (self.package / 'pet' / name).read_bytes())
        (self.pet / 'notes.txt').write_bytes(b'keep')
        self.run_installer('Uninstall')
        for name, data in self.old.items():
            self.assertEqual((self.pet / name).read_bytes(), data)
        self.assertEqual((self.pet / 'notes.txt').read_bytes(), b'keep')
        self.assertEqual(self.config.read_bytes(), b'# unchanged\nmodel="example"\n')

    def test_update_keeps_first_backup_and_repeated_install_is_safe(self):
        self.run_installer()
        before = json.loads((self.state / 'pet-installation.json').read_text(encoding='utf-8-sig'))
        meta_path = self.package / 'pet/pet.json'
        meta = json.loads(meta_path.read_text(encoding='utf-8'))
        meta['description'] = 'updated description'
        meta_path.write_text(json.dumps(meta), encoding='utf-8')
        self.refresh_manifest()
        self.run_installer()
        self.run_installer()
        after = json.loads((self.state / 'pet-installation.json').read_text(encoding='utf-8-sig'))
        self.assertEqual(before['original_files'], after['original_files'])
        self.assertEqual((self.pet / 'pet.json').read_bytes(), meta_path.read_bytes())
        self.run_installer('Uninstall')
        self.assertEqual((self.pet / 'pet.json').read_bytes(), self.old['pet.json'])

    def test_bad_source_hash_is_rejected_before_mutation(self):
        (self.package / 'pet/pet.json').write_bytes(b'tampered')
        self.run_installer(ok=False)
        self.assertEqual((self.pet / 'pet.json').read_bytes(), self.old['pet.json'])
        self.assertFalse((self.state / 'pet-installation.json').exists())

    def test_full_suite_owned_pet_requires_its_existing_uninstaller(self):
        full_record = self.state.parent / 'installation.json'
        full_record.write_text(json.dumps({'files': [{'path': str(self.pet / 'pet.json')}]}), encoding='utf-8')
        result = self.run_installer(ok=False)
        self.assertIn('full suite', result.stderr.lower())
        self.assertEqual((self.pet / 'pet.json').read_bytes(), self.old['pet.json'])

    def test_local_changes_block_update_and_uninstall(self):
        self.run_installer()
        (self.pet / 'pet.json').write_bytes(b'user edit')
        self.run_installer(ok=False)
        self.run_installer('Uninstall', ok=False)
        self.assertEqual((self.pet / 'pet.json').read_bytes(), b'user edit')

    def test_corrupt_backup_blocks_uninstall_without_touching_pet(self):
        self.run_installer()
        record = json.loads((self.state / 'pet-installation.json').read_text(encoding='utf-8-sig'))
        Path(record['original_files'][0]['backup_path']).write_bytes(b'corrupt')
        self.run_installer('Uninstall', ok=False)
        for name in NAMES:
            self.assertEqual((self.pet / name).read_bytes(), (self.package / 'pet' / name).read_bytes())

    def test_failed_second_file_replacement_restores_first_file(self):
        self.run_installer()
        original = {name: (self.pet / name).read_bytes() for name in NAMES}
        original_record = (self.state / 'pet-installation.json').read_bytes()
        atlas_path = self.package / 'pet/spritesheet.webp'
        atlas_path.write_bytes(atlas_path.read_bytes() + b'test update')
        self.refresh_manifest()
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.CreateFileW.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32,
                                      ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p]
        kernel.CreateFileW.restype = ctypes.c_void_p
        kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        handle = kernel.CreateFileW(str(self.pet / 'pet.json'), 0x80000000, 1, None, 3, 0x80, None)
        self.assertNotEqual(handle, ctypes.c_void_p(-1).value)
        try:
            self.run_installer(ok=False)
        finally:
            kernel.CloseHandle(handle)
        self.assertEqual((self.state / 'pet-installation.json').read_bytes(), original_record)
        for name, data in original.items():
            self.assertEqual((self.pet / name).read_bytes(), data)

    def test_new_install_uninstall_removes_only_installed_files(self):
        for name in NAMES:
            (self.pet / name).unlink()
        self.run_installer()
        (self.pet / 'user-file.txt').write_bytes(b'keep')
        self.run_installer('Uninstall')
        self.assertFalse((self.pet / 'pet.json').exists())
        self.assertFalse((self.pet / 'spritesheet.webp').exists())
        self.assertEqual((self.pet / 'user-file.txt').read_bytes(), b'keep')
