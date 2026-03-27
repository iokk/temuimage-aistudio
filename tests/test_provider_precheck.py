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
            probe_func=lambda base, key, model, capability: (True, "ok"),
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
            probe_func=lambda base, key, model, capability: (True, "ok"),
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
            probe_func=lambda base, key, model, capability: (False, "no channel"),
        )
        self.assertIn("no channel", reasons[0])

    def test_probe_receives_capability_name(self):
        seen = []

        def probe(base, key, model, capability):
            seen.append((model, capability))
            return True, "ok"

        validate_relay_models(
            provider="relay",
            relay_base="https://relay.example.com/v1",
            relay_key="sk-test",
            image_model="seedream-5.0",
            analysis_model="gemini-3.1-flash-lite-preview",
            required_capabilities=["image_analysis", "image_generate"],
            probe_func=probe,
        )

        self.assertEqual(
            seen,
            [
                ("gemini-3.1-flash-lite-preview", "image_analysis"),
                ("seedream-5.0", "image_generate"),
            ],
        )

    def test_shared_analysis_model_is_probed_once(self):
        seen = []

        def probe(base, key, model, capability):
            seen.append((model, capability))
            return True, "ok"

        validate_relay_models(
            provider="relay",
            relay_base="https://relay.example.com/v1",
            relay_key="sk-test",
            image_model="seedream-5.0",
            analysis_model="gemini-3.1-flash-lite-preview",
            required_capabilities=[
                "image_analysis",
                "title_from_image",
                "text_generation",
            ],
            probe_func=probe,
        )

        self.assertEqual(len(seen), 1)
        self.assertEqual(seen[0][0], "gemini-3.1-flash-lite-preview")

    def test_image_generation_probe_can_use_catalog_level_success(self):
        reasons = validate_relay_models(
            provider="relay",
            relay_base="https://relay.example.com/v1",
            relay_key="sk-test",
            image_model="seedream-5.0",
            analysis_model="gemini-3.1-flash-lite-preview",
            required_capabilities=["image_generate"],
            probe_func=lambda base, key, model, capability: (True, "ok"),
        )
        self.assertEqual(reasons, [])


if __name__ == "__main__":
    unittest.main()
