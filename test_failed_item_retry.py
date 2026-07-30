import io
import unittest
import urllib.error
from unittest.mock import Mock, patch
from datetime import datetime, timedelta

from PIL import Image

import app


class FailedItemRetryTests(unittest.TestCase):
    def test_default_image_timeout_allows_slow_generation(self):
        self.assertGreaterEqual(app.GEMINI_IMAGE_REQUEST_TIMEOUT_SECONDS, 300)

    def test_classifies_gateway_timeout_without_exposing_html(self):
        now = datetime(2026, 7, 29, 10, 0, 0)

        result = app.classify_image_task_error(
            "<html><h1>504 Gateway Time-out</h1></html>", now=now
        )

        self.assertEqual(result["error_type"], "upstream_timeout")
        self.assertTrue(result["retryable"])
        self.assertNotIn("<html>", result["error"])
        self.assertEqual(
            result["retry_after_at"],
            (now + timedelta(seconds=app.IMAGE_RETRY_COOLDOWN_SECONDS)).isoformat(),
        )

    def test_sanitize_task_error_recognizes_gateway_time_out(self):
        result = app.sanitize_task_error("504 Gateway Time-out from nginx")

        self.assertEqual(result, "请求超时，请检查网络、代理或模型响应速度。")

    def test_classifies_sanitized_timeout_as_retryable(self):
        result = app.classify_image_task_error(
            "请求超时，请检查网络、代理或模型响应速度。"
        )

        self.assertEqual(result["error_type"], "upstream_timeout")
        self.assertTrue(result["retryable"])

    def test_sanitizer_removes_markup_credentials_and_explicit_secret(self):
        opaque_secret = "opaque-explicit-secret"
        result = app.sanitize_task_error(
            "<html>Authorization: Bearer bearer-value-123 "
            "sk-standalone-secret-123 " + opaque_secret + " upstream failed</html>",
            secrets=(opaque_secret,),
        )

        for leaked in (
            "<html>",
            "Bearer",
            "bearer-value-123",
            "sk-standalone-secret-123",
            opaque_secret,
        ):
            self.assertNotIn(leaked, result)

    def test_sanitizer_removes_credentials_from_every_url_component(self):
        result = app.sanitize_task_error(
            "failed https://url-user:url-password@relay.example/v1"
            "?token=query-secret#fragment-secret"
        )

        self.assertEqual(result, "failed https://relay.example/v1")
        for credential in (
            "url-user",
            "url-password",
            "query-secret",
            "fragment-secret",
        ):
            self.assertNotIn(credential, result)

    def test_sanitizer_handles_malformed_url_without_exposing_suffix_credentials(self):
        result = app.sanitize_task_error(
            "failed http://[?token=query-secret#fragment-secret"
        )

        self.assertEqual(result, "failed [REDACTED_URL]")

    def test_sanitizer_rejects_url_without_a_hostname(self):
        result = app.sanitize_task_error(
            "failed https:///url-user:url-password@relay.example/v1"
            "?token=query-secret#fragment-secret"
        )

        self.assertEqual(result, "failed [REDACTED_URL]")

    def test_http_client_errors_redact_the_active_opaque_secret(self):
        opaque_secret = "opaque-provider-secret-123"

        def upstream_error():
            return urllib.error.HTTPError(
                "https://relay.example/v1",
                400,
                "Bad Request",
                {},
                io.BytesIO(
                    f"<html>upstream echoed {opaque_secret}</html>".encode()
                ),
            )

        openai_client = app.OpenAIClient(
            opaque_secret,
            base_url="https://relay.example/v1",
        )
        with patch.object(
            app.urllib.request, "urlopen", side_effect=upstream_error()
        ):
            with self.assertRaises(Exception) as openai_failure:
                openai_client._openai_call("/responses", {}, retries=1)

        gemini_client = app.GeminiClient(
            opaque_secret,
            base_url="https://relay.example",
        )
        with patch.object(
            app.urllib.request, "urlopen", side_effect=upstream_error()
        ):
            with self.assertRaises(Exception) as gemini_failure:
                gemini_client._manual_generate_content(
                    "gemini-test",
                    [{"text": "test"}],
                    ["TEXT"],
                )

        sdk_client = app.GeminiClient(opaque_secret)

        def fail_sdk_call():
            raise RuntimeError(f"SDK echoed {opaque_secret}")

        with self.assertRaises(Exception) as sdk_failure:
            sdk_client._call(fail_sdk_call, retries=1)

        for message in (
            str(openai_failure.exception),
            str(gemini_failure.exception),
            str(sdk_failure.exception),
            openai_client.get_last_error(),
            sdk_client.get_last_error(),
        ):
            self.assertNotIn(opaque_secret, message)
            self.assertNotIn("<html>", message)
        gemini_client.client.close()
        sdk_client.client.close()

    def test_transient_api_errors_have_retry_metadata_and_safe_messages(self):
        now = datetime(2026, 7, 30, 10, 0, 0)
        cases = {
            "429": "rate_limited",
            "502": "upstream_timeout",
            "503": "upstream_timeout",
            "504": "upstream_timeout",
            "request timed out": "upstream_timeout",
        }

        for marker, expected_type in cases.items():
            with self.subTest(marker=marker):
                result = app.classify_image_task_error(
                    "<html>HTTP " + marker
                    + " Authorization: Bearer secret-bearer sk-hidden-token-123</html>",
                    now=now,
                )

                self.assertEqual(result["error_type"], expected_type)
                self.assertTrue(result["retryable"])
                self.assertEqual(
                    result["retry_after_at"],
                    (now + timedelta(seconds=app.IMAGE_RETRY_COOLDOWN_SECONDS)).isoformat(),
                )
                self.assertNotIn("<html>", result["error"])
                self.assertNotIn("Bearer", result["error"])
                self.assertNotIn("sk-hidden-token-123", result["error"])

    def test_retry_wait_uses_latest_failed_item_cooldown(self):
        now = datetime(2026, 7, 29, 10, 0, 0)
        task = {
            "item_results": [
                {
                    "status": "error",
                    "prompt": "retry this item",
                    "retryable": True,
                    "retry_after_at": (now + timedelta(seconds=42)).isoformat(),
                }
            ]
        }

        self.assertEqual(app.failed_item_retry_wait_seconds(task, now=now), 42)

    def test_retry_wait_migrates_legacy_timeout_item(self):
        failed_at = datetime(2026, 7, 29, 10, 0, 0)
        task = {
            "updated_at": failed_at.isoformat(),
            "item_results": [
                {
                    "status": "error",
                    "prompt": "retry this legacy item",
                    "error": "请求超时，请检查网络、代理或模型响应速度。",
                }
            ],
        }

        wait = app.failed_item_retry_wait_seconds(
            task, now=failed_at + timedelta(seconds=30)
        )

        self.assertEqual(wait, app.IMAGE_RETRY_COOLDOWN_SECONDS - 30)

    def test_builds_payload_from_failed_items_only(self):
        task = {
            "id": "task-123",
            "type": "smart",
            "summary": "五张商品组图",
            "payload": {
                "provider_id": "provider-1",
                "image_paths": ["input.png"],
                "enable_title": True,
                "title_info": "product title",
                "total": 3,
            },
            "item_results": [
                {
                    "type_name": "白底图",
                    "index": 1,
                    "prompt": "white background",
                    "status": "done",
                    "file_path": "done.png",
                },
                {
                    "type_name": "场景图",
                    "index": 1,
                    "prompt": "lifestyle scene",
                    "status": "error",
                    "error": "504 Gateway Time-out",
                },
                {
                    "type_name": "细节图",
                    "index": 1,
                    "prompt": "product detail",
                    "status": "error",
                    "error": "504 Gateway Time-out",
                },
            ],
        }

        payload, error = app.build_failed_item_retry_payload(task)

        self.assertEqual(error, "")
        self.assertEqual(payload["total"], 2)
        self.assertEqual(payload["retry_parent_id"], "task-123")
        self.assertEqual(
            [item["prompt"] for item in payload["retry_items"]],
            ["lifestyle scene", "product detail"],
        )
        self.assertFalse(payload["enable_title"])
        self.assertEqual(payload["title_info"], "")
        self.assertEqual(payload["provider_id"], "provider-1")

    def test_retry_payload_and_action_share_mixed_item_eligibility(self):
        task = {
            "id": "mixed-retry",
            "type": "smart",
            "payload": {"provider_id": "provider-1"},
            "item_results": [
                {"status": "done", "prompt": "already succeeded", "retryable": True},
                {"status": "error", "prompt": "permanent failure", "retryable": False},
                {"status": "error", "prompt": "explicit transient", "retryable": True},
                {
                    "status": "error",
                    "prompt": "legacy rate limit",
                    "error": "429 too many requests",
                },
                {"status": "error", "prompt": "legacy permanent", "error": "bad input"},
            ],
        }

        payload, error = app.build_failed_item_retry_payload(task)

        self.assertEqual(error, "")
        self.assertEqual(
            [item["prompt"] for item in payload["retry_items"]],
            ["explicit transient", "legacy rate limit"],
        )
        self.assertTrue(app.has_retryable_failed_items(task))

        task["item_results"] = task["item_results"][:2]
        self.assertFalse(app.has_retryable_failed_items(task))

    def test_rejects_task_without_retryable_failures(self):
        payload, error = app.build_failed_item_retry_payload(
            {
                "type": "smart",
                "item_results": [
                    {"status": "done", "prompt": "successful prompt"}
                ],
            }
        )

        self.assertIsNone(payload)
        self.assertIn("没有可重试", error)

    def test_rejects_retry_during_cooldown(self):
        task = {
            "type": "smart",
            "item_results": [
                {
                    "status": "error",
                    "prompt": "retry later",
                    "retryable": True,
                    "retry_after_at": (
                        datetime.now() + timedelta(seconds=60)
                    ).isoformat(),
                }
            ],
        }

        payload, error = app.build_failed_item_retry_payload(task)

        self.assertIsNone(payload)
        self.assertIn("冷却", error)

    def test_rejects_non_smart_task(self):
        payload, error = app.build_failed_item_retry_payload(
            {"type": "text_to_image", "item_results": []}
        )

        self.assertIsNone(payload)
        self.assertIn("智能组图", error)

    def test_retry_execution_preserves_success_when_an_item_fails(self):
        class FakeClient:
            def generate_image(self, refs, prompt, *args):
                if prompt == "fails upstream":
                    raise RuntimeError("504 Gateway Time-out")
                return Image.new("RGB", (32, 32), "white")

        task = {
            "id": "retry-task",
            "type": "smart",
            "payload": {
                "provider_id": "provider-1",
                "image_paths": ["input.png"],
                "retry_items": [
                    {"type_name": "白底图", "index": 1, "prompt": "works"},
                    {"type_name": "场景图", "index": 1, "prompt": "fails upstream"},
                ],
                "image_language": "zh",
            },
        }
        provider = {"api_key": "test", "image_model": "gpt-image-2"}
        execution = Mock()
        execution.task = task

        with (
            patch.object(app, "get_provider_by_id", return_value=provider),
            patch.object(
                app,
                "load_image_paths",
                return_value=[Image.new("RGB", (32, 32), "gray")],
            ),
            patch.object(app, "create_ai_client", return_value=FakeClient()),
            patch.object(app, "persist_image_for_task", return_value="result.png"),
        ):
            result = app._execute_smart_task(execution)

        self.assertTrue(result["partial"])
        self.assertEqual(result["files"], ["result.png"])
        self.assertEqual(
            {item["status"] for item in result["item_results"]},
            {"done", "error"},
        )
        failed = next(
            item for item in result["item_results"] if item["status"] == "error"
        )
        self.assertEqual(failed["error_type"], "upstream_timeout")
        self.assertTrue(failed["retryable"])
        self.assertEqual(execution.checkpoint.call_count, 2)

    def test_openai_image_calls_disable_immediate_retries(self):
        client = app.OpenAIClient("test-key", model="gpt-image-2")
        image = Image.new("RGB", (32, 32), "white")

        with patch.object(client, "_openai_call", return_value={}) as call:
            client._images_edits("prompt", [image], "1024x1024", "medium")

        self.assertEqual(call.call_args.kwargs["retries"], 1)

    def test_openai_text_to_image_disables_immediate_retries(self):
        client = app.OpenAIClient("test-key", model="gpt-image-2")
        generated = Image.new("RGB", (32, 32), "white")

        with (
            patch.object(client, "_openai_call", return_value={}) as call,
            patch.object(client, "_extract_openai_image", return_value=generated),
        ):
            result = client.generate_image([], "a product photo")

        self.assertIs(result, generated)
        self.assertEqual(call.call_args.kwargs["retries"], 1)


if __name__ == "__main__":
    unittest.main()
