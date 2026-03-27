from __future__ import annotations

import unittest

from temu_core.ui_content import (
    build_admin_mode_notice,
    build_feature_catalog,
    build_page_sections,
    build_result_summary,
    build_workspace_actions,
)


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

    def test_batch_page_sections_follow_new_structure(self):
        sections = build_page_sections("combo")
        self.assertEqual(
            [item["key"] for item in sections],
            ["assets", "types", "brief", "compliance", "generate"],
        )

    def test_smart_page_sections_follow_new_structure(self):
        sections = build_page_sections("smart")
        self.assertEqual(
            [item["key"] for item in sections],
            ["assets", "types", "generate"],
        )

    def test_result_summary_marks_partial_success(self):
        summary = build_result_summary(
            title="标题优化结果",
            success_count=2,
            total_count=3,
            token_count=120,
            warning_count=1,
            error_count=1,
        )
        self.assertEqual(summary["state"], "partial")
        self.assertIn("2 / 3", summary["headline"])

    def test_workspace_actions_match_four_core_features(self):
        actions = build_workspace_actions()
        self.assertEqual(len(actions), 4)
        self.assertEqual(actions[0]["target"], "批量出图")


if __name__ == "__main__":
    unittest.main()
