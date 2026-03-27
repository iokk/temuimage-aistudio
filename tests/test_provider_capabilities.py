from __future__ import annotations

import unittest

from temu_core.provider_capabilities import (
    get_model_capabilities,
    get_translation_provider_message,
    model_supports,
)


class ProviderCapabilitiesTest(unittest.TestCase):
    def test_gemini_relay_model_supports_full_multimodal_flow(self):
        caps = get_model_capabilities("relay", "gemini-3.1-flash-image-preview")
        self.assertTrue(caps["image_generate"])
        self.assertTrue(caps["image_translate"])
        self.assertTrue(caps["image_analysis"])
        self.assertTrue(caps["title_from_image"])

    def test_flash_lite_preview_is_analysis_only_model(self):
        caps = get_model_capabilities("relay", "gemini-3.1-flash-lite-preview")
        self.assertFalse(caps["image_generate"])
        self.assertTrue(caps["image_analysis"])
        self.assertTrue(caps["title_from_image"])
        self.assertTrue(caps["text_generation"])

    def test_seedream_5_supports_translation_but_not_analysis(self):
        caps = get_model_capabilities("relay", "seedream-5.0")
        self.assertTrue(caps["image_generate"])
        self.assertTrue(caps["image_translate"])
        self.assertFalse(caps["image_analysis"])

    def test_seedream_46_is_generation_only_by_default(self):
        caps = get_model_capabilities("relay", "seedream-4.6")
        self.assertTrue(caps["image_generate"])
        self.assertFalse(caps["image_translate"])

    def test_unknown_model_defaults_to_false(self):
        self.assertFalse(model_supports("relay", "unknown-model", "image_translate"))

    def test_translation_message_for_unsupported_relay_model(self):
        message = get_translation_provider_message("relay", "seedream-4.6")
        self.assertIn("不支持图片翻译出图", message)


if __name__ == "__main__":
    unittest.main()
