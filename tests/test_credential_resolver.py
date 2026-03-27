from __future__ import annotations

import unittest

from temu_core.credential_resolver import resolve_runtime_credentials


class CredentialResolverTest(unittest.TestCase):
    def test_prefers_user_relay_when_selected(self):
        result = resolve_runtime_credentials(
            preferred_provider="relay",
            use_own_credentials=True,
            own_provider="relay",
            own_gemini_key="",
            own_relay_key="user-relay-key",
            own_relay_base="https://relay.example.com/v1",
            own_relay_model="gemini-3.1-flash-image-preview",
            system_gemini_key="AIzaSystem",
            system_relay_key="system-relay-key",
            system_relay_base="https://system-relay.example.com/v1",
            system_relay_model="seedream-5.0",
        )
        self.assertEqual(result["provider"], "relay")
        self.assertEqual(result["scope"], "user")
        self.assertEqual(result["api_key"], "user-relay-key")

    def test_uses_system_relay_when_no_personal_credentials(self):
        result = resolve_runtime_credentials(
            preferred_provider="relay",
            use_own_credentials=False,
            own_provider="",
            own_gemini_key="",
            own_relay_key="",
            own_relay_base="",
            own_relay_model="",
            system_gemini_key="AIzaSystem",
            system_relay_key="system-relay-key",
            system_relay_base="https://system-relay.example.com/v1",
            system_relay_model="seedream-5.0",
        )
        self.assertEqual(result["provider"], "relay")
        self.assertEqual(result["scope"], "system")
        self.assertEqual(result["api_key"], "system-relay-key")

    def test_uses_personal_gemini_when_selected(self):
        result = resolve_runtime_credentials(
            preferred_provider="gemini",
            use_own_credentials=True,
            own_provider="gemini",
            own_gemini_key="AIzaUser",
            own_relay_key="",
            own_relay_base="",
            own_relay_model="",
            system_gemini_key="AIzaSystem",
            system_relay_key="system-relay-key",
            system_relay_base="https://system-relay.example.com/v1",
            system_relay_model="seedream-5.0",
        )
        self.assertEqual(result["provider"], "gemini")
        self.assertEqual(result["scope"], "user")
        self.assertEqual(result["api_key"], "AIzaUser")


if __name__ == "__main__":
    unittest.main()
