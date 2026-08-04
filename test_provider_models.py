import os
import unittest
from unittest.mock import patch

import app


class ProviderModelCatalogTests(unittest.TestCase):
    def test_gemini_client_initializes_with_an_inherited_socks_proxy(self):
        proxy_environment = {
            "all_proxy": "socks5://127.0.0.1:1080",
            "http_proxy": "http://127.0.0.1:1081",
            "https_proxy": "http://127.0.0.1:1081",
        }

        with patch.dict(os.environ, proxy_environment, clear=True):
            client = app.GeminiClient(api_key="fake-key")

        client.client.close()

    def test_normalizes_gemini_and_openai_shapes(self):
        catalog = app._normalize_model_catalog(
            [
                {
                    "name": "models/gemini-2.5-flash",
                    "displayName": "Gemini Flash",
                    "supportedGenerationMethods": ["generateContent"],
                },
                {"id": "gpt-image-2", "name": "GPT Image 2"},
            ]
        )

        self.assertEqual([item["id"] for item in catalog], ["gemini-2.5-flash", "gpt-image-2"])
        self.assertIn("vision", catalog[0]["roles"])
        self.assertIn("image", catalog[1]["roles"])

    def test_fetched_models_are_preferred_for_each_role(self):
        provider = {
            "model_catalog": [
                {"id": "relay-title", "name": "Relay Title", "roles": ["title", "vision"]},
                {"id": "relay-image", "name": "Relay Image", "roles": ["image"]},
            ]
        }

        self.assertEqual(app._provider_model_choices(provider, "title")[0], "relay-title")
        self.assertEqual(app._provider_model_choices(provider, "image")[0], "relay-image")

    def test_nonempty_upstream_catalog_does_not_mix_builtin_candidates(self):
        provider = {
            "model_catalog": [
                {"id": "relay-title", "name": "Relay Title", "roles": ["title"]},
                {"id": "relay-image", "name": "Relay Image", "roles": ["image"]},
            ]
        }

        self.assertEqual(app._provider_model_choices(provider, "title"), ["relay-title"])
        self.assertEqual(app._provider_model_choices(provider, "image"), ["relay-image"])

    def test_catalog_refresh_preserves_user_role_overrides(self):
        current = [
            {
                "id": "relay-model",
                "name": "Old name",
                "roles": ["title"],
                "role_overrides": ["vision"],
            }
        ]
        refreshed = [
            {"id": "relay-model", "name": "New name", "roles": ["title"]},
        ]

        merged = app._merge_model_catalog(current, refreshed)

        self.assertEqual(merged[0]["name"], "New name")
        self.assertEqual(merged[0]["role_overrides"], ["vision"])
        self.assertEqual(app._effective_model_roles(merged[0]), ["vision"])

    def test_current_assignment_remains_selectable_when_missing_from_catalog(self):
        provider = {
            "title_model": "removed-model",
            "model_catalog": [
                {"id": "relay-title", "name": "Relay Title", "roles": ["title"]},
            ],
        }

        self.assertEqual(
            app._provider_model_choices(provider, "title"),
            ["relay-title", "removed-model"],
        )

    def test_binding_state_distinguishes_ready_mismatch_stale_and_unset(self):
        provider = {
            "title_model": "text-model",
            "vision_model": "text-model",
            "image_model": "removed-image",
            "model_catalog": [
                {"id": "text-model", "name": "Text", "roles": ["title"]},
            ],
        }

        self.assertEqual(app._provider_model_binding_state(provider, "title"), "ready")
        self.assertEqual(app._provider_model_binding_state(provider, "vision"), "mismatch")
        self.assertEqual(app._provider_model_binding_state(provider, "image"), "stale")
        provider["image_model"] = ""
        self.assertEqual(app._provider_model_binding_state(provider, "image"), "unset")

    def test_model_bindings_are_valid_only_when_every_role_is_ready_or_stale(self):
        provider = {
            "title_model": "text-model",
            "vision_model": "vision-model",
            "image_model": "image-model",
            "model_catalog": [
                {"id": "text-model", "roles": ["title"]},
                {"id": "vision-model", "roles": ["vision"]},
                {"id": "image-model", "roles": ["image"]},
            ],
        }

        self.assertEqual(app._invalid_provider_model_bindings(provider), [])
        provider["vision_model"] = "text-model"
        self.assertEqual(app._invalid_provider_model_bindings(provider), ["vision"])

    def test_fetch_provider_models_uses_demo_catalog_without_network(self):
        provider = app.build_demo_provider()
        catalog = app.fetch_provider_models(provider)

        self.assertTrue(catalog)
        self.assertTrue(any(item["id"] == "gpt-image-2" for item in catalog))

    def test_official_gemini_model_discovery_uses_only_api_key_header(self):
        calls = []

        def fake_request(endpoint, headers):
            calls.append((endpoint, headers))
            return {"models": [{"name": "models/gemini-2.5-flash"}]}

        provider = {"provider_type": "gemini", "api_key": "gemini-key"}
        with patch.object(app, "_request_model_endpoint", side_effect=fake_request):
            app.fetch_provider_models(provider)

        self.assertEqual(
            calls,
            [
                (
                    "https://generativelanguage.googleapis.com/v1beta/models",
                    {"Accept": "application/json", "x-goog-api-key": "gemini-key"},
                )
            ],
        )

    def test_relay_falls_back_to_openai_compatible_models_endpoint(self):
        provider = {
            "provider_type": "relay",
            "api_key": "test-key",
            "base_url": "https://relay.example/v1",
        }
        calls = []

        def fake_request(endpoint, headers):
            calls.append((endpoint, headers))
            if endpoint.endswith("/v1/models"):
                return {"data": [{"id": "gpt-image-2"}]}
            raise RuntimeError("not found")

        with patch.object(app, "_request_model_endpoint", side_effect=fake_request):
            catalog = app.fetch_provider_models(provider)

        self.assertEqual(catalog[0]["id"], "gpt-image-2")
        self.assertEqual(
            calls,
            [
                (
                    "https://relay.example/v1beta/models",
                    {"Accept": "application/json", "x-goog-api-key": "test-key"},
                ),
                (
                    "https://relay.example/v1/models",
                    {"Accept": "application/json", "Authorization": "Bearer test-key"},
                ),
            ],
        )

    def test_model_endpoint_switches_protocol_versions(self):
        self.assertEqual(
            app._model_endpoint("https://relay.example/v1beta", "/v1/models"),
            "https://relay.example/v1/models",
        )
        self.assertEqual(
            app._model_endpoint("https://relay.example/v1", "/v1beta/models"),
            "https://relay.example/v1beta/models",
        )


if __name__ == "__main__":
    unittest.main()
