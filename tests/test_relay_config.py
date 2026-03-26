from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

import app
from temu_core.relay_config import (
    has_system_service_access,
    resolve_relay_runtime_config,
)


class RelayConfigTest(unittest.TestCase):
    def test_system_service_access_true_when_relay_is_configured(self):
        settings = {
            "relay_api_base": "https://relay.example.com/v1",
            "relay_api_key": "sk-relay-123",
        }
        self.assertTrue(has_system_service_access(False, settings))

    def test_system_service_access_false_without_gemini_or_relay(self):
        settings = {"relay_api_base": "", "relay_api_key": ""}
        self.assertFalse(has_system_service_access(False, settings))

    def test_system_service_access_true_when_gemini_is_available(self):
        settings = {"relay_api_base": "", "relay_api_key": ""}
        self.assertTrue(has_system_service_access(True, settings))

    def test_resolve_relay_runtime_config_uses_saved_key_when_input_empty(self):
        settings = {
            "relay_api_base": "https://relay.example.com/v1/",
            "relay_api_key": "sk-saved",
            "relay_default_image_model": "imagine_x_1",
        }
        relay_key, relay_base, relay_model = resolve_relay_runtime_config(
            settings, "", "", ""
        )
        self.assertEqual(relay_key, "sk-saved")
        self.assertEqual(relay_base, "https://relay.example.com/v1")
        self.assertEqual(relay_model, "imagine_x_1")

    def test_resolve_relay_runtime_config_prefers_user_input(self):
        settings = {
            "relay_api_base": "https://relay.example.com/v1",
            "relay_api_key": "sk-saved",
            "relay_default_image_model": "imagine_x_1",
        }
        relay_key, relay_base, relay_model = resolve_relay_runtime_config(
            settings,
            "sk-user",
            "https://user-relay.example.com/v1/",
            "flux_dev",
        )
        self.assertEqual(relay_key, "sk-user")
        self.assertEqual(relay_base, "https://user-relay.example.com/v1")
        self.assertEqual(relay_model, "flux_dev")


class RelayImageClientTest(unittest.TestCase):
    @patch("app.requests.post")
    def test_relay_image_client_has_generate_image(self, mock_post):
        response = MagicMock()
        response.status_code = 200
        response.text = '{"choices": []}'
        response.json.return_value = {
            "choices": [],
            "usage": {"total_tokens": 12},
        }
        mock_post.return_value = response

        client = app.RelayImageClient(
            api_key="sk-test",
            model="gemini-3.1-flash-image-preview",
            base_url="https://newapi.aisonnet.org/v1",
        )

        self.assertTrue(hasattr(client, "generate_image"))
        result = client.generate_image(refs=[], prompt="test image")
        self.assertIsNone(result)
        self.assertEqual(client.get_tokens_used(), 12)

    @patch("app.requests.get")
    def test_extract_image_supports_markdown_wrapped_url(self, mock_get):
        png_bytes = (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde"
            b"\x00\x00\x00\x0cIDATx\x9cc``\xf8\xcf\xc0\x00\x00\x03\x01\x01\x00\xc9\xfe\x92\xef\x00\x00\x00\x00IEND\xaeB`\x82"
        )
        response = MagicMock()
        response.content = png_bytes
        response.raise_for_status.return_value = None
        mock_get.return_value = response

        client = app.RelayImageClient(
            api_key="sk-test",
            model="gemini-3.1-flash-image-preview",
            base_url="https://newapi.aisonnet.org/v1",
        )
        payload = {
            "choices": [
                {
                    "message": {
                        "content": "![antigravity_image](https://example.com/test.png)"
                    }
                }
            ]
        }

        image = client._extract_image_from_response(payload)

        self.assertIsNotNone(image)


class RelayModelCatalogTest(unittest.TestCase):
    def test_priority_models_are_present_in_expected_order(self):
        model_keys = list(app.RELAY_IMAGE_MODELS.keys())
        self.assertEqual(
            model_keys[:4],
            [
                "gemini-3.1-flash-image-preview",
                "seedream-5.0",
                "seedream-4.6",
                "z-image-turbo",
            ],
        )
        self.assertEqual(
            app.DEFAULT_SETTINGS["relay_default_image_model"],
            "gemini-3.1-flash-image-preview",
        )


if __name__ == "__main__":
    unittest.main()
