from __future__ import annotations

import unittest

from temu_core.branding import (
    APP_COMPANY,
    APP_EN_NAME,
    APP_NAME,
    APP_VERSION,
    build_footer_meta,
)


class BrandingTest(unittest.TestCase):
    def test_branding_constants_match_latest_product_name(self):
        self.assertEqual(APP_NAME, "小白图 跨境电商出图系统")
        self.assertEqual(APP_EN_NAME, "AI Studio")
        self.assertEqual(APP_COMPANY, "深圳祖尔科技有限公司")
        self.assertTrue(APP_VERSION.startswith("v"))

    def test_footer_meta_contains_company_and_version(self):
        meta = build_footer_meta()
        self.assertIn(APP_COMPANY, meta["company_line"])
        self.assertIn(APP_VERSION, meta["version_line"])


if __name__ == "__main__":
    unittest.main()
