"""Forward the existing Codex hook and play one random completion clip."""
import hashlib
import json
import msvcrt
import os
from pathlib import Path
import random
import subprocess
import sys
import time
import wave
import winsound

ROOT = Path(__file__).resolve().parent


def record(event, **fields):
    # Never log notification content, prompts, or assistant responses.
    with (ROOT / 'playback.log').open('a', encoding='utf-8') as f:
        f.write(json.dumps({'time': time.strftime('%Y-%m-%d %H:%M:%S'),
                            'event': event, **fields}, ensure_ascii=False) + '\n')


def choose_clip(clips, previous):
    options = [c for c in clips if c['file'] != previous]
    return random.SystemRandom().choice(options or clips)


def event_key(payload):
    thread = payload.get('thread-id') or payload.get('thread_id')
    turn = payload.get('turn-id') or payload.get('turn_id')
    if thread and turn:
        return hashlib.sha256(f'{thread}:{turn}'.encode()).hexdigest()
    return None


def play(settings, payload=None, preview=False):
    lock_path = ROOT / 'playback.lock'
    with lock_path.open('a+b') as lock:
        if lock.tell() == 0:
            lock.write(b'0'); lock.flush()
        deadline = time.monotonic() + 30
        while True:
            lock.seek(0)
            try:
                msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
                break
            except OSError:
                if time.monotonic() > deadline:
                    record('queue-timeout'); return
                time.sleep(.1)
        try:
            state_file = ROOT / 'state.json'
            try:
                state = json.loads(state_file.read_text(encoding='utf-8'))
            except (OSError, ValueError):
                state = {}
            key = event_key(payload or {})
            seen = state.get('seen', [])
            if key and key in seen:
                record('duplicate-skipped'); return
            clip = choose_clip(settings['clips'], state.get('last_file'))
            sound = (ROOT / clip['file']).resolve()
            if sound.parent != (ROOT / 'audio').resolve():
                raise ValueError('Audio path outside installed clip folder')
            winsound.PlaySound(str(sound), winsound.SND_FILENAME | winsound.SND_NODEFAULT)
            if key:
                seen.append(key)
            state_file.write_text(json.dumps({'last_file': clip['file'], 'seen': seen[-100:]}), encoding='utf-8')
            record('preview-played' if preview else 'completion-played', clip=clip['file'])
        finally:
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)


def main():
    settings = json.loads((ROOT / 'settings.json').read_text(encoding='utf-8'))
    args = sys.argv[1:]
    if args == ['--self-test']:
        previous = None
        for _ in range(100):
            clip = choose_clip(settings['clips'], previous)
            assert clip['file'] != previous
            previous = clip['file']
        for clip in settings['clips']:
            with wave.open(str(ROOT / clip['file']), 'rb') as w:
                assert 0 < w.getnframes() / w.getframerate() < 30
        assert event_key({'thread-id': 'test', 'turn-id': 'one'}) == event_key({'thread_id': 'test', 'turn_id': 'one'})
        print('PASS: four WAV files, 100 no-repeat choices, notification deduplication keys')
        return
    if args == ['--preview']:
        play(settings, preview=True)
        return
    # Preserve the original plugin notification verb and all appended arguments.
    previous = settings.get('previous_notify', [])
    if previous:
        try:
            subprocess.Popen(previous + args, stdin=subprocess.DEVNULL,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             creationflags=subprocess.CREATE_NO_WINDOW)
        except OSError as error:
            record('previous-hook-error', error_type=type(error).__name__)
    payload = None
    for arg in reversed(args):
        try:
            candidate = json.loads(arg)
            if isinstance(candidate, dict):
                payload = candidate; break
        except ValueError:
            pass
    if payload is None:
        record('no-notification-payload'); return
    if payload.get('type') != 'agent-turn-complete':
        record('ignored-event', notification_type=str(payload.get('type', 'unknown'))[:80])
        return
    play(settings, payload)


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        record('error', error_type=type(error).__name__)
        sys.exit(1)
