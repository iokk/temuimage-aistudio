import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app


class ProviderSecretPersistenceTests(unittest.TestCase):
    def make_provider(self):
        return {
            "id": "provider-1",
            "name": "Secure Provider",
            "provider_type": "openai",
            "base_url": "https://api.example/v1",
            "api_key": "encrypted-old-value",
            "secret_storage": "encrypted",
            "keychain_account": "provider-provider-1",
            "title_model": "gpt-4o-mini",
            "vision_model": "gpt-4o-mini",
            "image_model": "gpt-image-2",
        }

    def test_replacement_secret_never_enters_serialized_provider_state(self):
        provider = self.make_provider()
        replacement = "opaque-replacement-secret"

        with (
            patch.object(app, "resolve_provider_api_key", return_value="old-secret"),
            patch.object(app, "keychain_available", return_value=False),
            patch.object(app, "encrypted_storage_available", return_value=True),
            patch.object(app, "encrypt_secret", return_value="encrypted-new-value"),
        ):
            prepared, errors, _ = app.prepare_provider_for_save(
                provider, replacement
            )

        serialized = json.dumps({"providers": [prepared]})
        self.assertEqual(errors, [])
        self.assertNotIn(replacement, serialized)
        self.assertEqual(prepared["secret_storage"], "encrypted")
        self.assertEqual(prepared["api_key"], "encrypted-new-value")
        self.assertEqual(provider["api_key"], "encrypted-old-value")

    def test_invalid_replacement_is_rejected_before_secret_storage(self):
        provider = self.make_provider()
        provider["base_url"] = "not-a-url"

        with patch.object(app, "persist_provider_secret") as persist:
            prepared, errors, _ = app.prepare_provider_for_save(
                provider, "replacement-secret"
            )

        self.assertIsNone(prepared)
        self.assertTrue(errors)
        persist.assert_not_called()

    def test_provider_base_url_rejects_embedded_credentials_and_suffix_data(self):
        invalid_urls = (
            "https://user:password@relay.example/v1",
            "https://relay.example/v1?token=secret",
            "https://relay.example/v1#secret",
        )

        for base_url in invalid_urls:
            with self.subTest(base_url=base_url):
                errors = app.validate_provider_config(
                    "Provider",
                    "openai",
                    "test-key",
                    base_url,
                )
                self.assertTrue(errors)

    def test_new_secret_persistence_fails_closed_without_secure_storage(self):
        provider = self.make_provider()

        with (
            patch.object(app, "keychain_available", return_value=False),
            patch.object(app, "encrypted_storage_available", return_value=False),
        ):
            with self.assertRaisesRegex(RuntimeError, "安全保存"):
                app.persist_provider_secret(provider, "must-not-be-plain")

        self.assertNotEqual(provider["api_key"], "must-not-be-plain")

    def test_environment_provider_never_persists_its_secret(self):
        secret = "environment-only-provider-secret"
        with tempfile.TemporaryDirectory() as temporary_directory:
            providers_file = Path(temporary_directory) / "providers.json"
            with (
                patch.object(app, "PROVIDERS_FILE", providers_file),
                patch.object(app, "keychain_available", return_value=False),
                patch.object(app, "encrypted_storage_available", return_value=False),
                patch.dict(
                    os.environ,
                    {
                        "GOOGLE_API_KEY": secret,
                        "GEMINI_API_KEY": "",
                        "XIAOBAITU_DEMO_MODE": "0",
                    },
                    clear=False,
                ),
            ):
                data = app.get_providers()
                provider = data["providers"][0]

                self.assertEqual(provider.get("secret_storage"), "environment")
                self.assertEqual(provider.get("api_key"), "")
                self.assertEqual(app.resolve_provider_api_key(provider), secret)
                self.assertNotIn(secret, providers_file.read_text(encoding="utf-8"))

    def test_secret_storage_notice_names_the_actual_backend(self):
        self.assertEqual(
            app.provider_secret_storage_notice({"secret_storage": "keychain"}),
            "API Key 已安全保存到 Keychain。",
        )
        self.assertEqual(
            app.provider_secret_storage_notice({"secret_storage": "encrypted"}),
            "API Key 已加密保存。",
        )
        self.assertEqual(
            app.provider_secret_storage_notice({"secret_storage": "runtime"}),
            "",
        )


class ServerAccessSecurityTests(unittest.TestCase):
    def test_server_mode_without_access_password_fails_closed(self):
        with (
            patch.object(app, "SERVER_MODE", True),
            patch.dict(os.environ, {}, clear=False),
            patch.object(app.st, "error") as show_error,
            patch.object(
                app.st,
                "stop",
                side_effect=RuntimeError("streamlit stopped"),
            ),
        ):
            os.environ.pop("APP_ACCESS_PASSWORD", None)

            with self.assertRaisesRegex(RuntimeError, "streamlit stopped"):
                app.require_access_password()

        self.assertIn("APP_ACCESS_PASSWORD", show_error.call_args.args[0])


if __name__ == "__main__":
    unittest.main(verbosity=2)
