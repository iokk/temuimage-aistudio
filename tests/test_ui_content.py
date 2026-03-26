from __future__ import annotations

import unittest

from temu_core.ui_content import build_admin_mode_notice, build_feature_catalog


class UIContentTest(unittest.TestCase):
    def test_feature_catalog_starts_with_workspace(self):
        catalog = build_feature_catalog()
        self.assertEqual(catalog[0]["key"], "workspace")
        self.assertEqual(catalog[1]["key"], "combo")
        self.assertEqual(catalog[2]["key"], "smart")

    def test_admin_mode_notice_for_system_service_access_is_non_blocking(self):
        notice = build_admin_mode_notice(has_service_access=True, team_ready=False)
        self.assertEqual(notice["level"], "info")
        self.assertIn("管理员模式", notice["title"])
        self.assertIn("系统中转站", notice["body"])

    def test_admin_mode_notice_for_team_ready_highlights_team_mode(self):
        notice = build_admin_mode_notice(has_service_access=True, team_ready=True)
        self.assertEqual(notice["level"], "success")
        self.assertIn("团队模式", notice["title"])


if __name__ == "__main__":
    unittest.main()
