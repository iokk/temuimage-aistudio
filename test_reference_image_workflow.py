import tempfile
import unittest
from pathlib import Path

from PIL import Image

import app


class ReferenceImageWorkflowTests(unittest.TestCase):
    def test_missing_reference_path_fails_explicitly(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "missing-reference.png"

            with self.assertRaisesRegex(
                RuntimeError,
                "missing-reference.png",
            ):
                app.load_image_paths([str(missing)])

    def test_corrupt_reference_path_fails_explicitly(self):
        with tempfile.TemporaryDirectory() as tmp:
            corrupt = Path(tmp) / "corrupt-reference.png"
            corrupt.write_bytes(b"not an image")

            with self.assertRaisesRegex(
                RuntimeError,
                "corrupt-reference.png",
            ):
                app.load_image_paths([str(corrupt)])

    def test_valid_reference_paths_preserve_order_and_convert_to_rgb(self):
        with tempfile.TemporaryDirectory() as tmp:
            first = Path(tmp) / "first.png"
            second = Path(tmp) / "second.png"
            Image.new("RGBA", (10, 8), (255, 0, 0, 128)).save(first)
            Image.new("L", (6, 4), 64).save(second)

            images = app.load_image_paths([str(first), str(second)])

            self.assertEqual([image.size for image in images], [(10, 8), (6, 4)])
            self.assertEqual([image.mode for image in images], ["RGB", "RGB"])
            self.assertEqual(images[0].getpixel((0, 0)), (255, 0, 0))
            self.assertEqual(images[1].getpixel((0, 0)), (64, 64, 64))


if __name__ == "__main__":
    unittest.main()
