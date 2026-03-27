from __future__ import annotations

import unittest

from temu_core.relay_text_client import RelayTextClient


class RelayTextClientTest(unittest.TestCase):
    def test_extract_text_from_string_content(self):
        client = RelayTextClient("sk-test", "gemini-3.1-flash-image-preview")
        payload = {
            "choices": [
                {"message": {"content": "hello relay"}},
            ]
        }
        self.assertEqual(client.extract_text_from_response(payload), "hello relay")

    def test_extract_text_from_list_content(self):
        client = RelayTextClient("sk-test", "gemini-3.1-flash-image-preview")
        payload = {
            "choices": [
                {
                    "message": {
                        "content": [
                            {"type": "text", "text": "hello"},
                            {"type": "text", "text": "relay"},
                        ]
                    }
                },
            ]
        }
        self.assertEqual(client.extract_text_from_response(payload), "hello\nrelay")

    def test_parse_json_response_from_fenced_block(self):
        client = RelayTextClient("sk-test", "gemini-3.1-flash-image-preview")
        text = '```json\n{"name": "Bottle"}\n```'
        self.assertEqual(client.parse_json_response(text, {}), {"name": "Bottle"})

    def test_extract_and_translate_response_returns_expected_shape(self):
        client = RelayTextClient("sk-test", "gemini-3.1-flash-image-preview")
        client.generate_text = lambda refs, prompt, max_tokens=1200, temperature=0.2: (
            '{"language":"en","source_lines":["FAST SHIPPING"],"translated_lines":["FAST SHIPPING"]}'
        )
        result = client.extract_and_translate_image_text(
            object(), source_lang="auto", target_lang="English"
        )
        self.assertEqual(result["language"], "en")
        self.assertEqual(result["source_lines"], ["FAST SHIPPING"])


if __name__ == "__main__":
    unittest.main()
