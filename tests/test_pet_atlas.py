"""Protect the v2 layout, original rows and transparent-cell contract."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('pet_atlas', ROOT / 'scripts/pet_atlas.py')
atlas = importlib.util.module_from_spec(spec)
spec.loader.exec_module(atlas)


def marker(value):
    # Synthetic test markers only; production artwork comes from imagegen.
    image = Image.new('RGBA', (192, 208))
    image.paste((value, 30, 90, 255), (70, 80, 90, 100))
    return image


class PetAtlasTests(unittest.TestCase):
    def setUp(self):
        self.old = Image.open(ROOT / 'pet/spritesheet.webp').convert('RGBA')
        self.old = self.old.crop((0, 0, 1536, 1872))
        self.gaze = [marker(i + 40) for i in range(16)]
        self.completion = [marker(i + 80) for i in range(4)]

    def test_v1_remains_supported(self):
        result = atlas.validate_atlas(self.old, 1)
        self.assertTrue(result['ok'], result['errors'])
        self.assertEqual(result['used_frames'], 57)

    def test_upgrade_preserves_other_eight_rows_and_gaze_order(self):
        image = atlas.compose_upgrade(self.old, self.gaze, self.completion)
        self.assertEqual(image.size, (1536, 2288))
        for row in [0, 1, 2, 4, 5, 6, 7, 8]:
            bounds = (0, row * 208, 1536, (row + 1) * 208)
            self.assertEqual(image.crop(bounds).tobytes(), self.old.crop(bounds).tobytes())
        self.assertEqual(image.getpixel((70, 9 * 208 + 80)), (40, 30, 90, 255))
        self.assertEqual(image.getpixel((70, 10 * 208 + 80)), (48, 30, 90, 255))
        self.assertEqual(image.getpixel((7 * 192 + 70, 10 * 208 + 80)), (55, 30, 90, 255))
        self.assertEqual(image.crop((4 * 192, 624, 1536, 832)).getbbox(), None)
        result = atlas.validate_atlas(image, 2, require_new_motion=True)
        self.assertTrue(result['ok'], result['errors'])
        self.assertEqual(result['used_frames'], 73)

    def test_cannot_enable_v2_with_only_metadata(self):
        result = atlas.validate_atlas(self.old, 2)
        self.assertFalse(result['ok'])
        self.assertTrue(any('1536x2288' in e for e in result['errors']))

    def test_missing_or_repeated_gaze_is_rejected(self):
        image = atlas.compose_upgrade(self.old, self.gaze, self.completion)
        image.paste((0, 0, 0, 0), (0, 9 * 208, 192, 10 * 208))
        self.assertFalse(atlas.validate_atlas(image, 2)['ok'])
        repeated = atlas.compose_upgrade(self.old, [self.gaze[0]] * 16, self.completion)
        self.assertFalse(atlas.validate_atlas(repeated, 2, require_new_motion=True)['ok'])

    def test_static_completion_is_rejected_for_motion_upgrade(self):
        image = atlas.compose_upgrade(self.old, self.gaze, [self.completion[0]] * 4)
        self.assertFalse(atlas.validate_atlas(image, 2, require_new_motion=True)['ok'])

    def test_unused_pixels_and_hidden_rgb_are_rejected(self):
        image = atlas.compose_upgrade(self.old, self.gaze, self.completion)
        image.putpixel((1535, 0), (90, 80, 70, 255))
        self.assertFalse(atlas.validate_atlas(image, 2)['ok'])
        image.putpixel((1535, 0), (90, 80, 70, 0))
        result = atlas.validate_atlas(image, 2)
        self.assertFalse(result['ok'])
        self.assertTrue(any('hidden RGB' in e for e in result['errors']))

    def test_wrong_frame_count_is_rejected_before_assembly(self):
        with self.assertRaises(ValueError):
            atlas.compose_upgrade(self.old, self.gaze[:-1], self.completion)
