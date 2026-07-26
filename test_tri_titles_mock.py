# -*- coding: utf-8 -*-
"""TEMU 三语标题解析/生成 mock 测试（不发真实请求）。"""
import json
import unittest
from unittest import mock

import app


FAKE_JSON = {
    "titles": [
        {"lang": "zh", "title": "保温杯" * 55, "chars": 999},
        {
            "lang": "es",
            "title": "Termo de acero inoxidable " * 7,
            "chars": 1,
            "back_translation_zh": "不锈钢保温杯，双层真空，适合日常通勤使用。",
        },
        {
            "lang": "fr",
            "title": "Gourde isotherme en acier inoxydable " * 5,
            "back_translation_zh": "不锈钢保温壶，双层真空，适合户外与办公场景。",
        },
    ],
    "issues": [],
}
FAKE_TEXT = "```json\n" + json.dumps(FAKE_JSON, ensure_ascii=False) + "\n```"


class TriTitleTests(unittest.TestCase):
    def test_parse_structure_and_python_char_counts(self):
        parsed = app.parse_tri_language_titles(FAKE_TEXT)
        entries = parsed["entries"]
        self.assertEqual([e["lang"] for e in entries], ["zh", "es", "fr"])
        for e in entries:
            # 字符数必须是 Python len()，不信任模型自报的 chars
            self.assertEqual(e["chars"], len(e["title"]))
        self.assertTrue(entries[1]["back_translation_zh"])
        self.assertTrue(entries[2]["back_translation_zh"])
        valid, reason, details = app._validate_tri_title_output(parsed)
        self.assertTrue(valid, reason)

    def test_missing_back_translation_invalid(self):
        bad = {"titles": [{"lang": "es", "title": "x" * 160}], "issues": []}
        parsed = app.parse_tri_language_titles(json.dumps(bad))
        valid, reason, _ = app._validate_tri_title_output(parsed)
        self.assertFalse(valid)

    def test_exception_rule_via_issues(self):
        data = {
            "titles": [
                {"lang": "zh", "title": "z" * 160},
                {"lang": "es", "title": "e" * 160, "back_translation_zh": "回译"},
            ],
            "issues": ["法语：该品类合规词不足，无法在150-200字符内产出合规标题"],
        }
        parsed = app.parse_tri_language_titles(json.dumps(data, ensure_ascii=False))
        valid, reason, _ = app._validate_tri_title_output(parsed)
        self.assertTrue(valid, reason)
        text = app.format_titles_text(
            app.merge_titles_and_issues({"titles": parsed["entries"], "issues": parsed["issues"]})
        )
        self.assertIn("⚠️", text)

    def test_generate_titles_text_path_mocked(self):
        client = app.GeminiClient(api_key="fake-key")
        with mock.patch.object(app.GeminiClient, "_text_request", return_value=FAKE_TEXT):
            result = client.generate_titles("不锈钢保温杯 500ml 双层真空", "")
        self.assertTrue(result["success"], result.get("error_message"))
        self.assertEqual(len(result["titles"]), 3)
        self.assertEqual({t["lang"] for t in result["titles"]}, {"zh", "es", "fr"})

    def test_generate_titles_vision_path_mocked(self):
        client = app.GeminiClient(api_key="fake-key")
        with mock.patch.object(app.GeminiClient, "_vision_request", return_value=FAKE_TEXT):
            result = client.generate_titles_from_image(["fake-image"], "保温杯")
        self.assertTrue(result["success"], result.get("error_message"))
        self.assertEqual(len(result["titles"]), 3)

    def test_format_titles_text_layout_and_legacy_strings(self):
        parsed = app.parse_tri_language_titles(FAKE_TEXT)
        text = app.format_titles_text(parsed["entries"])
        self.assertIn("中文 —", text)
        self.assertIn("Español —", text)
        self.assertIn("Français —", text)
        self.assertEqual(text.count("中文回译:"), 2)
        # 旧历史记录里的纯字符串标题不报错
        legacy = app.format_titles_text(["old english title one", "旧标题"])
        self.assertIn("old english title one", legacy)


if __name__ == "__main__":
    unittest.main(verbosity=2)
