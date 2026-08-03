import os
import tempfile
import unittest
from pathlib import Path

from PIL import Image


class NormalizeSuiteImageTests(unittest.TestCase):
    def _normalize(self, source, stem="suite-image", **kwargs):
        destination = Path(self.tmp.name) / "output"
        return self.normalize_suite_image(source, destination, stem, **kwargs)

    def setUp(self):
        from suite_output import normalize_suite_image

        self.normalize_suite_image = normalize_suite_image
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def _assert_standard_metadata(self, result):
        self.assertEqual(
            set(result), {"path", "format", "width", "height", "bytes", "dpi"}
        )
        self.assertEqual((result["width"], result["height"]), (1600, 1600))
        self.assertEqual(result["dpi"], (72, 72))
        self.assertLessEqual(result["bytes"], 2 * 1024 * 1024)

        path = Path(result["path"])
        self.assertTrue(path.is_file())
        self.assertEqual(path.stat().st_size, result["bytes"])
        expected_extensions = {"PNG": ".png", "JPEG": ".jpg"}
        self.assertEqual(path.suffix.lower(), expected_extensions[result["format"]])
        with Image.open(path) as saved:
            self.assertEqual(saved.size, (1600, 1600))
            self.assertEqual(saved.format, result["format"])
            self.assertAlmostEqual(saved.info["dpi"][0], 72, delta=0.1)
            self.assertAlmostEqual(saved.info["dpi"][1], 72, delta=0.1)

    def test_horizontal_image_is_contained_and_padded_without_cropping(self):
        source = Image.new("RGB", (800, 400), (200, 20, 40))

        result = self._normalize(source, "horizontal")

        self._assert_standard_metadata(result)
        self.assertEqual(result["format"], "JPEG")
        with Image.open(result["path"]).convert("RGB") as saved:
            self.assertEqual(saved.getpixel((800, 0)), (255, 255, 255))
            self.assertGreater(saved.getpixel((800, 400))[0], 150)
            self.assertLess(saved.getpixel((800, 400))[1], 50)

    def test_vertical_path_image_is_contained_and_padded_without_cropping(self):
        source_path = Path(self.tmp.name) / "vertical-source.png"
        Image.new("RGB", (400, 800), (20, 90, 210)).save(source_path)

        result = self._normalize(source_path, "vertical")

        self._assert_standard_metadata(result)
        self.assertEqual(result["format"], "JPEG")
        with Image.open(result["path"]).convert("RGB") as saved:
            self.assertEqual(saved.getpixel((0, 800)), (255, 255, 255))
            self.assertLess(saved.getpixel((400, 800))[0], 50)
            self.assertGreater(saved.getpixel((400, 800))[2], 150)

    def test_transparent_image_prefers_png_and_preserves_alpha(self):
        source = Image.new("RGBA", (400, 200), (40, 100, 220, 128))

        result = self._normalize(source, "transparent", prefer_png=True)

        self._assert_standard_metadata(result)
        self.assertEqual(result["format"], "PNG")
        with Image.open(result["path"]) as saved:
            self.assertEqual(saved.mode, "RGBA")
            self.assertEqual(saved.getpixel((800, 0))[3], 0)
            self.assertEqual(saved.getpixel((800, 800))[3], 128)

    def test_noisy_photo_falls_back_to_compressed_jpeg_under_size_limit(self):
        source = Image.frombytes("RGB", (1600, 1600), os.urandom(1600 * 1600 * 3))

        result = self._normalize(source, "noisy-photo")

        self._assert_standard_metadata(result)
        self.assertEqual(result["format"], "JPEG")

    def test_oversized_transparent_png_falls_back_to_white_backed_jpeg(self):
        source = Image.frombytes(
            "RGBA", (1600, 1600), os.urandom(1600 * 1600 * 4)
        )
        source.paste((0, 0, 0, 0), (0, 0, 80, 80))

        result = self._normalize(source, "noisy-transparent", prefer_png=True)

        self._assert_standard_metadata(result)
        self.assertEqual(result["format"], "JPEG")
        with Image.open(result["path"]).convert("RGB") as saved:
            self.assertTrue(all(channel > 245 for channel in saved.getpixel((40, 40))))


if __name__ == "__main__":
    unittest.main()
