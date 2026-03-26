from __future__ import annotations

import unittest

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


if __name__ == "__main__":
    unittest.main()
