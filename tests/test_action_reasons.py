from __future__ import annotations

import unittest

from temu_core.action_reasons import (
    combo_analysis_reasons,
    combo_generate_reasons,
    smart_generate_reasons,
    title_generate_reasons,
    translate_generate_reasons,
)


class ActionReasonsTest(unittest.TestCase):
    def test_combo_analysis_requires_images(self):
        reasons = combo_analysis_reasons(image_count=0)
        self.assertTrue(reasons)
        self.assertIn("上传至少 1 张商品图", reasons[0])

    def test_combo_generate_requires_requirements_and_not_generating(self):
        reasons = combo_generate_reasons(req_count=0, generating=False)
        self.assertIn("先生成图需文案", reasons[0])

    def test_smart_generate_requires_images_name_and_type(self):
        reasons = smart_generate_reasons(image_count=0, product_name="", total_count=0)
        self.assertEqual(len(reasons), 3)

    def test_title_generate_requires_image_or_text(self):
        reasons = title_generate_reasons("🖼️ 图片分析", product_info="", image_count=0)
        self.assertIn("上传至少 1 张图片", reasons[0])

    def test_translate_generate_explains_capability_mismatch(self):
        reasons = translate_generate_reasons(
            upload_count=1,
            need_text=True,
            need_image=True,
            provider="relay",
            text_supported=True,
            image_supported=False,
        )
        self.assertIn("当前模型不支持翻译出图", reasons[-1])


if __name__ == "__main__":
    unittest.main()
