import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from provider_acceptance import redact_acceptance_error, verify_provider


class FakeClient:
    def __init__(self, secret):
        self.secret = secret
        self.paths = []

    def test_connection(self):
        return "OK"

    def _openai_call(
        self, path, payload=None, timeout_seconds=60, retries=1, **_kwargs
    ):
        self.paths.append(path)
        return {
            "object": "response",
            "status": "completed",
            "output": [
                {
                    "type": "message",
                    "content": [{"type": "output_text", "text": "OK"}],
                }
            ],
        }

    def generate_image(self, *_args, **_kwargs):
        image = Image.new("RGB", (32, 32), "#f43f5e")
        image.putpixel((0, 0), (15, 23, 42))
        return image


class SecretEchoingResponsesClient(FakeClient):
    def _openai_call(
        self, path, payload=None, timeout_seconds=60, retries=1, **_kwargs
    ):
        self.paths.append(path)
        return {
            "object": self.secret,
            "status": "completed",
            "output": ["OK"],
        }


class FakeApplication:
    def __init__(self, secret="sk-super-secret-acceptance"):
        self.secret = secret
        self.client = FakeClient(secret)

    def resolve_provider_api_key(self, _provider):
        return self.secret

    def fetch_provider_models(self, _provider):
        return [
            {"id": "gpt-image-2", "name": "GPT Image 2"},
            {"id": "gpt-5.6-sol", "name": "GPT 5.6 Sol"},
        ]

    def create_ai_client(self, provider, **_kwargs):
        self.last_provider = provider
        return self.client

    @staticmethod
    def sanitize_task_error(message):
        return str(message)


class FailingApplication(FakeApplication):
    def fetch_provider_models(self, _provider):
        raise RuntimeError(
            f"<html>Authorization: Bearer {self.secret} upstream failed</html>"
        )


class RawSecretFailingApplication(FakeApplication):
    def fetch_provider_models(self, _provider):
        raise RuntimeError(f"upstream rejected {self.secret}")


class DoubleDecryptGuardApplication(FakeApplication):
    def resolve_provider_api_key(self, provider):
        storage = provider.get("secret_storage")
        if storage == "encrypted":
            if provider.get("api_key") != "encrypted-local-value":
                raise AssertionError("resolved secret was decrypted twice")
            return self.secret
        if storage == "runtime":
            return provider.get("api_key", "")
        raise AssertionError(f"unexpected secret storage: {storage}")

    def fetch_provider_models(self, provider):
        self.resolve_provider_api_key(provider)
        return super().fetch_provider_models(provider)

    def create_ai_client(self, provider, **kwargs):
        self.resolve_provider_api_key(provider)
        return super().create_ai_client(provider, **kwargs)


class ProviderAcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.provider = {
            "id": "provider-1",
            "name": "Acceptance Provider",
            "provider_type": "openai",
            "base_url": "https://relay.example/v1",
            "api_key": "encrypted-local-value",
            "secret_storage": "encrypted",
            "image_model": "gpt-image-2",
            "title_model": "gpt-5.6-sol",
        }

    def test_report_separates_capabilities_without_exposing_the_secret(self):
        application = FakeApplication()

        report = verify_provider(self.provider, application)

        self.assertTrue(report["ok"])
        self.assertEqual(report["checks"]["models"]["count"], 2)
        self.assertTrue(
            report["checks"]["models"]["configured_image_model_present"]
        )
        self.assertTrue(report["checks"]["text"]["ok"])
        self.assertTrue(report["checks"]["responses"]["ok"])
        self.assertFalse(report["checks"]["image"]["requested"])
        self.assertEqual(application.client.paths, ["/responses"])

        serialized = json.dumps(report, ensure_ascii=False)
        self.assertNotIn(application.secret, serialized)
        self.assertNotIn("encrypted-local-value", serialized)
        self.assertNotIn("Bearer", serialized)
        self.assertNotIn("api_key", serialized.lower())

    def test_live_image_check_records_dimensions_and_writes_the_requested_file(self):
        application = FakeApplication()
        with tempfile.TemporaryDirectory() as temporary_directory:
            output = Path(temporary_directory) / "acceptance.png"

            report = verify_provider(
                self.provider,
                application,
                include_live_image=True,
                image_output=output,
            )

            self.assertTrue(report["checks"]["image"]["ok"])
            self.assertEqual(report["checks"]["image"]["size"], [32, 32])
            self.assertEqual(report["checks"]["image"]["output"], str(output))
            with Image.open(output) as saved:
                self.assertEqual(saved.size, (32, 32))

    def test_failure_error_is_bounded_and_redacted(self):
        application = FailingApplication()

        report = verify_provider(self.provider, application)

        error = report["checks"]["models"]["error"]
        self.assertFalse(report["ok"])
        self.assertNotIn(application.secret, error)
        self.assertNotIn("Bearer", error)
        self.assertNotIn("<html>", error)
        self.assertLessEqual(len(error), 180)

    def test_redactor_removes_bearer_and_sk_style_secrets(self):
        message = (
            "<b>Authorization: Bearer token-value-123</b> "
            "api_key=sk-another-secret-value"
        )

        redacted = redact_acceptance_error(message)

        self.assertNotIn("Bearer", redacted)
        self.assertNotIn("token-value-123", redacted)
        self.assertNotIn("sk-another-secret-value", redacted)
        self.assertNotIn("<b>", redacted)

    def test_redactor_removes_query_and_fragment_credentials_from_urls(self):
        redacted = redact_acceptance_error(
            "failed https://relay.example/v1"
            "?token=query-secret#fragment-secret"
        )

        self.assertEqual(redacted, "failed https://relay.example/v1")

    def test_redactor_handles_malformed_url_without_exposing_suffix_credentials(self):
        redacted = redact_acceptance_error(
            "failed http://[?token=query-secret#fragment-secret"
        )

        self.assertEqual(redacted, "failed [REDACTED_URL]")

    def test_redactor_rejects_url_without_a_hostname(self):
        redacted = redact_acceptance_error(
            "failed https:///url-user:url-password@relay.example/v1"
            "?token=query-secret#fragment-secret"
        )

        self.assertEqual(redacted, "failed [REDACTED_URL]")

    def test_report_redacts_the_resolved_secret_even_without_a_known_prefix(self):
        application = RawSecretFailingApplication("opaque-provider-secret-123")

        report = verify_provider(self.provider, application)

        serialized = json.dumps(report, ensure_ascii=False)
        self.assertNotIn(application.secret, serialized)

    def test_report_redacts_secret_echoed_in_responses_metadata(self):
        application = FakeApplication("opaque-provider-secret-123")
        application.client = SecretEchoingResponsesClient(application.secret)

        report = verify_provider(self.provider, application)

        self.assertTrue(report["ok"])
        self.assertEqual(report["checks"]["responses"]["object"], "[REDACTED]")
        self.assertNotIn(
            application.secret,
            json.dumps(report, ensure_ascii=False),
        )

    def test_report_omits_credentials_from_every_base_url_component(self):
        provider = dict(self.provider)
        provider["base_url"] = (
            "https://url-user:url-password@relay.example:8443/v1"
            "?token=opaque-url-secret-123#fragment-secret-456"
        )

        report = verify_provider(provider, FakeApplication())

        self.assertEqual(
            report["provider"]["base_url"],
            "https://relay.example:8443/v1",
        )
        serialized = json.dumps(report, ensure_ascii=False)
        for credential in (
            "url-user",
            "url-password",
            "opaque-url-secret-123",
            "fragment-secret-456",
        ):
            self.assertNotIn(credential, serialized)

    def test_malformed_base_url_does_not_abort_the_structured_report(self):
        provider = dict(self.provider)
        provider["base_url"] = "https://["

        report = verify_provider(provider, FakeApplication())

        self.assertTrue(report["ok"])
        self.assertEqual(report["provider"]["base_url"], "")
        self.assertTrue(report["checks"]["models"]["ok"])
        self.assertTrue(report["checks"]["text"]["ok"])
        self.assertTrue(report["checks"]["responses"]["ok"])

    def test_base_url_without_a_hostname_is_omitted_from_the_report(self):
        provider = dict(self.provider)
        provider["base_url"] = (
            "https:///url-user:url-password@relay.example/v1"
            "?token=query-secret#fragment-secret"
        )

        report = verify_provider(provider, FakeApplication())

        self.assertEqual(report["provider"]["base_url"], "")
        serialized = json.dumps(report, ensure_ascii=False)
        for credential in (
            "url-user",
            "url-password",
            "query-secret",
            "fragment-secret",
        ):
            self.assertNotIn(credential, serialized)

    def test_runtime_provider_secret_is_not_decrypted_twice(self):
        application = DoubleDecryptGuardApplication()

        report = verify_provider(self.provider, application)

        self.assertTrue(report["ok"])
        self.assertEqual(application.last_provider["secret_storage"], "runtime")
        self.assertEqual(application.last_provider["api_key"], application.secret)


if __name__ == "__main__":
    unittest.main(verbosity=2)
