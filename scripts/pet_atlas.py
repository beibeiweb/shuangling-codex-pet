"""Validate Codex v1/v2 atlases and assemble approved generated upgrade frames.

This module processes existing artwork; it does not generate sprite artwork.
Pillow is a development dependency, not an installer requirement.
"""
import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image

COUNTS = [6, 8, 8, 4, 5, 8, 6, 6, 6]
STATES = ['idle', 'running-right', 'running-left', 'waving', 'jumping',
          'failed', 'waiting', 'running', 'review']


def validate_atlas(source, version=1, require_new_motion=False):
    image = source.convert('RGBA')
    errors, rows = [], []
    if version not in (1, 2):
        return {'ok': False, 'errors': ['unsupported sprite version'], 'rows': [], 'used_frames': 0}
    height = 2288 if version == 2 else 1872
    if image.size != (1536, height):
        return {'ok': False, 'errors': [f'expected 1536x{height}, got {image.width}x{image.height}'],
                'rows': [], 'used_frames': 0}
    if 'A' not in source.getbands():
        errors.append('atlas requires an alpha channel')
    counts = COUNTS + ([8, 8] if version == 2 else [])
    states = STATES + (['gaze-0-7', 'gaze-8-15'] if version == 2 else [])
    gaze_hashes = []
    for row, (state, count) in enumerate(zip(states, counts)):
        hashes, boxes = [], []
        for col in range(8):
            cell = image.crop((col * 192, row * 208, (col + 1) * 192, (row + 1) * 208))
            alpha = cell.getchannel('A')
            visible = sum(alpha.histogram()[1:])
            if col < count:
                if visible < 50:
                    errors.append(f'{state} frame {col} is empty')
                if visible > 192 * 208 * .95:
                    errors.append(f'{state} frame {col} has an opaque background')
                digest = hashlib.sha256(cell.tobytes()).hexdigest()
                hashes.append(digest)
                boxes.append(alpha.getbbox())
                if row >= 9:
                    gaze_hashes.append(digest)
            elif visible:
                errors.append(f'{state} unused frame {col} is not transparent')
        rows.append({'state': state, 'used': count, 'unique_frames': len(set(hashes)), 'bounds': boxes})
    transparent = image.getchannel('A').point(lambda value: 255 if value == 0 else 0)
    residue = Image.composite(image.convert('RGB'), Image.new('RGB', image.size), transparent).getbbox()
    if residue:
        errors.append('fully transparent pixels contain hidden RGB')
    if require_new_motion:
        if version != 2 or len(set(gaze_hashes)) != 16:
            errors.append('upgrade needs 16 distinct gaze frames')
        if rows[3]['unique_frames'] != 4:
            errors.append('upgrade needs 4 distinct completion frames')
    return {'ok': not errors, 'errors': errors, 'version': version,
            'used_frames': sum(counts), 'unique_gaze_frames': len(set(gaze_hashes)), 'rows': rows}


def compose_upgrade(original, gaze, completion):
    if original.size not in [(1536, 1872), (1536, 2288)]:
        raise ValueError('original atlas has unsupported dimensions')
    if len(gaze) != 16 or len(completion) != 4:
        raise ValueError('exactly 16 gaze and 4 completion frames are required')
    if any(frame.size != (192, 208) or frame.mode != 'RGBA' for frame in [*gaze, *completion]):
        raise ValueError('frames must be 192x208 RGBA')
    result = Image.new('RGBA', (1536, 2288))
    result.paste(original.convert('RGBA').crop((0, 0, 1536, 1872)), (0, 0))
    result.paste((0, 0, 0, 0), (0, 624, 1536, 832))
    for i, frame in enumerate(completion):
        result.paste(frame, (i * 192, 624))
    for i, frame in enumerate(gaze):
        result.paste(frame, ((i % 8) * 192, (9 + i // 8) * 208))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('pet_folder', type=Path)
    parser.add_argument('--require-new-motion', action='store_true')
    parser.add_argument('--json-out', type=Path)
    args = parser.parse_args()
    meta = json.loads((args.pet_folder / 'pet.json').read_text(encoding='utf-8-sig'))
    sheet = (args.pet_folder / meta.get('spritesheetPath', 'spritesheet.webp')).resolve()
    if sheet.parent != args.pet_folder.resolve():
        raise ValueError('spritesheet must be inside the pet folder')
    with Image.open(sheet) as image:
        report = validate_atlas(image, meta.get('spriteVersionNumber', 1), args.require_new_motion)
    if args.json_out:
        args.json_out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k: v for k, v in report.items() if k != 'rows'}))
    raise SystemExit(0 if report['ok'] else 1)


if __name__ == '__main__':
    main()
