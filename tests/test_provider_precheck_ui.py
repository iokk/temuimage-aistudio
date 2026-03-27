from __future__ import annotations

import unittest

from temu_core.provider_precheck import describe_capability_reasons


class ProviderPrecheckUITest(unittest.TestCase):
    def test_non_relay_provider_has_no_static_capability_reasons(self):
        reasons = describe_capability_reasons(
            provider="gemini",
            image_model="gemini-2.5-flash-image",
            analysis_model="gemini-3.1-flash-lite-preview",
            required_capabilities=["image_generate"],
        )
        self.assertEqual(reasons, [])

    def test_relay_reports_unsupported_image_translate_capability(self):
        reasons = describe_capability_reasons(
            provider="relay",
            image_model="seedream-4.6",
            analysis_model="gemini-3.1-flash-lite-preview",
            required_capabilities=["image_translate"],
        )
        self.assertIn("不支持图片翻译出图", reasons[0])

    def test_relay_uses_analysis_model_for_title_capability(self):
        reasons = describe_capability_reasons(
            provider="relay",
            image_model="seedream-5.0",
            analysis_model="gemini-3.1-flash-lite-preview",
            required_capabilities=["title_from_image"],
        )
        self.assertEqual(reasons, [])


if __name__ == "__main__":
    unittest.main()
