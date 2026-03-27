from __future__ import annotations

import unittest

from temu_core.config_ui import (
    build_login_tab_labels,
    build_recommended_provider_templates,
    build_settings_sections,
)


class ConfigUITest(unittest.TestCase):
    def test_login_tabs_hide_system_config_in_admin_mode(self):
        tabs = build_login_tab_labels("admin_tool_mode")
        self.assertEqual(tabs, ["👤 个人模式", "🛠️ 团队/管理员"])

    def test_login_tabs_show_system_config_in_team_mode(self):
        tabs = build_login_tab_labels("team_mode")
        self.assertEqual(tabs, ["👤 个人模式", "🛠️ 团队/管理员"])

    def test_settings_sections_have_personal_and_system_blocks(self):
        sections = build_settings_sections()
        self.assertIn("personal", sections)
        self.assertIn("system", sections)
        self.assertIn("relay", sections["personal"])
        self.assertIn("relay", sections["system"])

    def test_recommended_provider_templates_exist(self):
        templates = build_recommended_provider_templates()
        self.assertEqual(len(templates), 2)
        self.assertIn("中转站", templates[0]["title"])


if __name__ == "__main__":
    unittest.main()
