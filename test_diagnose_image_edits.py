import io
import json
import unittest
from contextlib import redirect_stderr
from types import SimpleNamespace

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


if __name__ == "__main__":
    unittest.main(verbosity=2)
