import io
import json
import unittest
from contextlib import redirect_stderr
from types import SimpleNamespace
from unittest.mock import patch

from scripts import diagnose_image_edits


class DiagnoseImageEditsSafetyTests(unittest.TestCase):
    def test_paid_probe_requires_explicit_acknowledgement(self):
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            diagnose_image_edits.parse_args(["--image", "input.png"])

    def test_paid_probe_rejects_unbounded_request_settings(self):
        invalid_options = (
            ["--requests", "6"],
            ["--concurrency", "3"],
            ["--retries", "2"],
        )
        for options in invalid_options:
            with self.subTest(options=options):
                with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                    diagnose_image_edits.parse_args(
                        ["--allow-paid-requests", "--image", "input.png", *options]
                    )

    def test_start_event_never_contains_provider_url_credentials(self):
        provider = {
            "base_url": (
                "https://url-user:url-password@relay.example/v1"
                "?token=query-secret#fragment-secret"
            ),
            "image_model": "gpt-image-2",
        }
        args = SimpleNamespace(
            concurrency=1,
            requests=1,
            retries=0,
            quality="low",
            inter_request_delay=0,
        )

        event = diagnose_image_edits.build_start_event(provider, (32, 32), args)

        self.assertNotIn("base_url", event)
        serialized = json.dumps(event)
        for credential in (
            "url-user",
            "url-password",
            "query-secret",
            "fragment-secret",
        ):
            self.assertNotIn(credential, serialized)

    def test_paid_probe_accepts_provider_and_model_overrides(self):
        args = diagnose_image_edits.parse_args(
            [
                "--allow-paid-requests",
                "--image",
                "input.png",
                "--provider-id",
                "provider-2",
                "--model",
                "gpt-image-2-auto",
            ]
        )

        self.assertEqual(args.provider_id, "provider-2")
        self.assertEqual(args.model, "gpt-image-2-auto")

    def test_resolve_probe_provider_applies_model_without_mutating_saved_provider(self):
        saved_provider = {
            "id": "provider-2",
            "api_key": "secret",
            "image_model": "gpt-image-2",
        }
        args = SimpleNamespace(
            provider_id="provider-2",
            model="gpt-image-2-auto",
        )

        with patch.object(
            diagnose_image_edits.app,
            "get_provider_by_id",
            return_value=saved_provider,
        ):
            provider = diagnose_image_edits.resolve_probe_provider(args)

        self.assertEqual(provider["image_model"], "gpt-image-2-auto")
        self.assertEqual(saved_provider["image_model"], "gpt-image-2")


if __name__ == "__main__":
    unittest.main(verbosity=2)
