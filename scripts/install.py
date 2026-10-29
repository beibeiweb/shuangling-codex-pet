"""Per-user Windows installer; only the top-level Codex notify key is edited."""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tomllib

PACKAGE = Path(__file__).resolve().parents[1]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read_config(path):
    text = path.read_text(encoding='utf-8-sig') if path.exists() else ''
    return text, tomllib.loads(text)


def replace_notify(text, value):
    """Locate the root key, including multiline arrays, and validate all other values."""
    before = tomllib.loads(text)
    lines = text.splitlines(keepends=True)
    start = end = None
    for i, line in enumerate(lines):
        if re.match(r'^\s*\[', line):
            break
        if re.match(r'''^\s*(?:notify|"notify"|'notify')\s*=''', line):
            start = i
            for j in range(i + 1, len(lines) + 1):
                try:
                    parsed = tomllib.loads(''.join(lines[i:j]))
                except tomllib.TOMLDecodeError:
                    continue
                if 'notify' in parsed:
                    end = j
                    break
            break
    if 'notify' in before and start is None:
        raise ValueError('Unsupported notify syntax; configuration left unchanged')
    replacement = '' if value is None else 'notify = ' + json.dumps(value, ensure_ascii=True) + '\n'
    if start is None:
        result = replacement + text
    else:
        if end is None:
            raise ValueError('Cannot locate end of notify setting')
        result = ''.join(lines[:start]) + replacement + ''.join(lines[end:])
    after = tomllib.loads(result)
    expected = dict(before)
    if value is None:
        expected.pop('notify', None)
    else:
        expected['notify'] = value
    if after != expected:
        raise ValueError('Configuration verification failed')
    return result


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.shuangling-tmp')
    temp.write_bytes(data)
    os.replace(temp, path)


def locations(sandbox):
    if sandbox:
        base = Path(sandbox).resolve()
        return base / 'app', base / 'codex', base / 'Desktop', base / 'Programs'
    return (Path(os.environ['LOCALAPPDATA']) / 'ShuanglingCodexPet',
            Path(os.environ.get('CODEX_HOME', str(Path.home() / '.codex'))),
            None, Path(os.environ['APPDATA']) / 'Microsoft/Windows/Start Menu/Programs')


def shortcut_bytes(destination, target, icon):
    def quote(value):
        return "'" + str(value).replace("'", "''") + "'"
    destination.parent.mkdir(parents=True, exist_ok=True)
    command = ("$ErrorActionPreference='Stop';$s=New-Object -ComObject WScript.Shell;"
               "$l=$s.CreateShortcut(" + quote(destination) + ");"
               "$l.TargetPath=" + quote(target) + ";$l.WorkingDirectory=" + quote(target.parent) + ";"
               "$l.IconLocation=" + quote(str(icon) + ',0') + ";$l.Save()")
    command = '[Console]::OutputEncoding=[Text.Encoding]::UTF8;' + command
    encoded = base64.b64encode(command.encode('utf-16-le')).decode('ascii')
    result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-EncodedCommand', encoded],
                            capture_output=True, encoding='utf-8', errors='replace',
                            creationflags=subprocess.CREATE_NO_WINDOW)
    if result.returncode:
        raise RuntimeError('Shortcut creation failed: ' + result.stderr)
    data = destination.read_bytes()
    destination.unlink()
    return data


def run(action, sandbox=None):
    app, codex, desktop, programs = locations(sandbox)
    config = codex / 'config.toml'
    manifest_path = app / 'installation.json'
    if action == 'uninstall':
        if not manifest_path.exists():
            raise ValueError('No installation found')
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        text, parsed = read_config(config)
        if parsed.get('notify') != manifest['notify']:
            raise ValueError('notify changed after installation; restore it manually using installation.json')
        for item in manifest['files']:
            path = Path(item['path'])
            if path.exists() and sha(path.read_bytes()) != item['sha256']:
                raise ValueError('Installed file changed; preserve it before uninstalling: ' + str(path))
        updated = replace_notify(text, manifest['previous_notify'])
        write(config, updated.encode('utf-8'))
        for item in reversed(manifest['files']):
            path = Path(item['path'])
            if item['previous'] is not None:
                write(path, base64.b64decode(item['previous']))
            elif path.exists():
                path.unlink()
        manifest_path.unlink()
        # Runtime logs and user-added files are deliberately retained.
        print('Uninstalled. Previous pet files and notify hook restored; runtime logs retained.')
        return
    if manifest_path.exists():
        raise ValueError('Already installed. Uninstall this package before reinstalling/upgrading.')
    text, parsed = read_config(config)
    previous = parsed.get('notify')
    if previous is not None and (not isinstance(previous, list) or not all(isinstance(v, str) for v in previous)):
        raise ValueError('Expected notify to be an array of strings')
    pythonw = Path(sys.executable).with_name('pythonw.exe')
    if not pythonw.exists():
        raise ValueError('Install standard Windows Python 3.11+ including pythonw.exe')
    notify = [str(pythonw), str(app / 'voice/notify.py')]
    updated = replace_notify(text, notify)
    settings = json.loads((PACKAGE / 'voice/settings.json').read_text(encoding='utf-8'))
    settings['previous_notify'] = previous or []
    files = {}
    for folder in ['launcher', 'voice']:
        for source in (PACKAGE / folder).rglob('*'):
            if source.is_file() and source.suffix != '.pyc' and '__pycache__' not in source.parts:
                files[app / source.relative_to(PACKAGE)] = source.read_bytes()
    files[app / 'voice/settings.json'] = json.dumps(settings, ensure_ascii=False, indent=2).encode('utf-8')
    for name in ['pet.json', 'spritesheet.webp']:
        files[codex / 'pets/shuangling-white-dragon' / name] = (PACKAGE / 'pet' / name).read_bytes()
    if not sandbox:
        result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command',
                                 '[Console]::OutputEncoding=[Text.Encoding]::UTF8;[Environment]::GetFolderPath("Desktop")'],
                                capture_output=True, check=True, encoding='utf-8', creationflags=subprocess.CREATE_NO_WINDOW)
        desktop = Path(result.stdout.strip())
        temporary_link = app / 'shortcut-build.lnk'
        link_data = shortcut_bytes(temporary_link, app / 'launcher/DragonCodexBoot.exe', app / 'launcher/media/shuangling.ico')
        for folder in [desktop, programs]:
            files[folder / 'Shuangling - Codex.lnk'] = link_data
    records = [{'path': str(path), 'sha256': sha(data),
                'previous': base64.b64encode(path.read_bytes()).decode() if path.exists() else None}
               for path, data in files.items()]
    manifest = {'notify': notify, 'previous_notify': previous, 'files': records}
    # Local backups may contain the user's previous hook path; never publish this file.
    write(manifest_path, json.dumps(manifest, ensure_ascii=False).encode('utf-8'))
    try:
        for path, data in files.items():
            write(path, data)
        write(config, updated.encode('utf-8'))
    except Exception:
        for item in reversed(records):
            path = Path(item['path'])
            if item['previous'] is not None:
                write(path, base64.b64decode(item['previous']))
            elif path.exists() and sha(path.read_bytes()) == item['sha256']:
                path.unlink()
        manifest_path.unlink()
        raise
    print('Installed. Restart Codex and select the Shuangling pet. Use Shuangling - Codex for the startup animation.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['install', 'uninstall'])
    parser.add_argument('--sandbox-root', help='Isolated test root; skips shortcuts')
    args = parser.parse_args()
    try:
        run(args.action, args.sandbox_root)
    except Exception as error:
        print('ERROR:', error, file=sys.stderr)
        sys.exit(1)
