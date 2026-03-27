from __future__ import annotations

import unittest

from temu_core.provider_precheck import validate_relay_models


class ProviderPrecheckTest(unittest.TestCase):
    def test_returns_empty_for_non_relay_provider(self):
        reasons = validate_relay_models(
            provider="gemini",
            relay_base="",
            relay_key="",
            image_model="seedream-5.0",
            analysis_model="gemini-3.1-flash-lite-preview",
            required_capabilities=["image_generate"],
            probe_func=lambda base, key, model: (True, "ok"),
        )
        self.assertEqual(reasons, [])

    def test_reports_unsupported_capability(self):
        reasons = validate_relay_models(
            provider="relay",
            relay_base="https://relay.example.com/v1",
            relay_key="sk-test",
            image_model="seedream-4.6",
            analysis_model="gemini-3.1-flash-lite-preview",
            required_capabilities=["image_translate"],
            probe_func=lambda base, key, model: (True, "ok"),
        )
        self.assertIn("不支持图片翻译出图", reasons[0])

    def test_reports_unavailable_channel(self):
        reasons = validate_relay_models(
            provider="relay",
            relay_base="https://relay.example.com/v1",
            relay_key="sk-test",
            image_model="seedream-5.0",
            analysis_model="gemini-3.1-flash-lite-preview",
            required_capabilities=["image_generate"],
            probe_func=lambda base, key, model: (False, "no channel"),
        )
        self.assertIn("no channel", reasons[0])


if __name__ == "__main__":
    unittest.main()
