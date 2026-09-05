from pathlib import Path
import tempfile
import unittest
from PIL import Image
from scripts.blender.pimm_production.package_bento_web_review import encode_frame


class WebReviewTests(unittest.TestCase):
    def test_encoding_preserves_every_display_pixel_and_rejects_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            source, output = Path(folder) / 'source.png', Path(folder) / 'frame.webp'
            image = Image.new('RGB', (80, 40), (31, 107, 191))
            image.putpixel((3, 3), (201, 50, 17))
            image.save(source)
            record = encode_frame(source, output)
            self.assertEqual(Image.open(output).convert('RGB').tobytes(), image.tobytes())
            self.assertEqual(record['bytes'], output.stat().st_size)
            with self.assertRaises(FileExistsError):
                encode_frame(source, output)
