from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

import app
from temu_core.title_logic import (
    filter_titles_by_compliance,
    generate_titles_or_raise,
    should_attempt_title_generation,
)


class FakeTitleClient:
    def __init__(self, image_titles=None, text_titles=None, last_error=""):
        self.image_titles = image_titles or []
        self.text_titles = text_titles or []
        self.last_error = last_error
        self.calls = []

    def generate_titles_from_image(self, images, product_info="", template_prompt=None):
        self.calls.append(("image", len(images), product_info, template_prompt))
        return list(self.image_titles)

    def generate_titles(self, product_info, template_prompt):
        self.calls.append(("text", product_info, template_prompt))
        return list(self.text_titles)


class TitleLogicTest(unittest.TestCase):
    def test_should_attempt_title_generation_with_images_only(self):
        self.assertTrue(should_attempt_title_generation(True, [object()], ""))

    def test_generate_titles_prefers_image_flow_when_images_present(self):
        client = FakeTitleClient(image_titles=["EN1", "CN1", "EN2", "CN2"])

        titles = generate_titles_or_raise(client, [object()], "water bottle", "prompt")

        self.assertEqual(titles[:2], ["EN1", "CN1"])
        self.assertEqual(client.calls[0][0], "image")

    def test_generate_titles_uses_text_flow_when_no_images(self):
        client = FakeTitleClient(text_titles=["EN1", "CN1"])

        titles = generate_titles_or_raise(client, [], "water bottle", "prompt")

        self.assertEqual(titles, ["EN1", "CN1"])
        self.assertEqual(client.calls[0][0], "text")

    def test_generate_titles_raises_last_error_when_empty(self):
        client = FakeTitleClient(image_titles=[], last_error="api failed")

        with self.assertRaises(ValueError) as ctx:
            generate_titles_or_raise(client, [object()], "", "prompt")

        self.assertIn("api failed", str(ctx.exception))

    def test_filter_titles_by_compliance_drops_noncompliant_pairs(self):
        titles = ["Best Water Bottle", "最佳水瓶", "Travel Water Bottle", "旅行水瓶"]

        def checker(text, mode):
            if text.startswith("Best"):
                return False, [], "含绝对化词汇"
            return True, [], ""

        filtered, warnings = filter_titles_by_compliance(titles, checker, "strict")

        self.assertEqual(filtered, ["Travel Water Bottle", "旅行水瓶"])
        self.assertEqual(len(warnings), 1)
        self.assertIn("含绝对化词汇", warnings[0])


class GeminiClientModelSelectionTest(unittest.TestCase):
    @patch.object(app.GeminiClient, "_load_prompts_safe", return_value={})
    @patch("app.create_genai_client", return_value=MagicMock())
    def test_gemini_client_keeps_passed_model(self, _mock_client, _mock_prompts):
        client = app.GeminiClient("AIzaFake", model="gemini-3.1-pro")
        self.assertEqual(client.model, "gemini-3.1-pro")

    def test_title_text_model_uses_flash_lite_preview(self):
        self.assertEqual(app.TITLE_TEXT_MODEL, "gemini-3.1-flash-lite-preview")


if __name__ == "__main__":
    unittest.main()
