"""Regression tests for build-portrait.py's crop() on frames with no face.

A frame that carries no bright-pixel signal (solid background, blank scan,
a flat placeholder) used to divide by a zero weight sum in the
"bright-centroid" branch, producing NaN and then

    ValueError: cannot convert float NaN to integer

Tests load build-portrait.py by path because the filename is not a valid
module name.
"""
import contextlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

spec = importlib.util.spec_from_file_location('build_portrait', ROOT / 'build-portrait.py')
bp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bp)

from PIL import Image  # noqa: E402  (after the module load, keeps import order clear)


class FlatFrameCropTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)

    def flat_image(self, size=(800, 1000), colour=(128, 128, 128)):
        path = self.tmp / 'flat.png'
        Image.new('RGB', size, colour).save(path)
        return Image.open(path).convert('RGB')

    def test_crop_of_flat_frame_returns_a_box(self):
        """crop() must not raise on a frame with zero bright-pixel weight."""
        im = self.flat_image()
        with mock.patch.object(bp, 'face_box', return_value=None):
            cropped, box, how = bp.crop(im)

        self.assertEqual(how, 'bright-centroid')
        self.assertEqual(len(box), 4)
        self.assertTrue(all(isinstance(v, int) for v in box), box)
        x, y, nw, nh = box
        self.assertGreater(nw, 0)
        self.assertGreater(nh, 0)
        self.assertLessEqual(x + nw, im.size[0])
        self.assertLessEqual(y + nh, im.size[1])
        self.assertEqual(cropped.size, (nw, nh))
        # the crop keeps the portrait aspect ratio the glyph grid expects
        self.assertAlmostEqual(nw / nh, bp.TARGET, places=1)

    def test_flat_frame_is_centred(self):
        """The fallback centre keeps the crop in the middle of the frame."""
        im = self.flat_image()
        with mock.patch.object(bp, 'face_box', return_value=None):
            _, (x, y, nw, nh), _ = bp.crop(im)

        centre_x, centre_y = x + nw / 2, y + nh / 2
        self.assertAlmostEqual(centre_x / im.size[0], 0.5, delta=0.05)
        # the crop sits a little above centre (headroom), not off the frame
        self.assertLess(abs(centre_y / im.size[1] - 0.5), 0.15)

    def test_bright_blob_still_drives_the_centroid(self):
        """The zero-weight guard must not disturb the normal centroid path."""
        im = Image.new('RGB', (800, 1000), (0, 0, 0))
        for x in range(600, 660):
            for y in range(200, 260):
                im.putpixel((x, y), (255, 255, 255))
        with mock.patch.object(bp, 'face_box', return_value=None):
            _, (x, y, nw, nh), _ = bp.crop(im)

        self.assertLess(abs((x + nw / 2) - 630), nw / 2)
        self.assertLess(abs((y + nh / 2) - 230), nh / 2)

    def test_main_completes_on_a_flat_frame(self):
        """End to end: a flat photo still yields the 3036-glyph grid."""
        src = self.tmp / 'flat.png'
        Image.new('RGB', (800, 1000), (128, 128, 128)).save(src)
        assets = self.tmp / 'assets'
        assets.mkdir()

        with mock.patch.object(bp, 'face_box', return_value=None), \
                mock.patch.object(bp, 'ASSETS', assets), \
                mock.patch.object(sys, 'argv', ['build-portrait.py', str(src)]), \
                contextlib.redirect_stdout(io.StringIO()):
            bp.main()

        for theme in ('dark', 'light'):
            cells = json.loads((assets / ('portrait-%s.json' % theme)).read_text())
            self.assertEqual(len(cells), 3036)
            self.assertTrue(all(c['ch'] in ('0', '1') for c in cells))


if __name__ == '__main__':
    unittest.main()
