from __future__ import annotations

from pathlib import Path
import unittest


class RebuildSettingsPanelsTest(unittest.TestCase):
    def test_system_runtime_exposes_model_defaults_and_team_counts(self):
        runtime_text = Path("apps/api/routers/system.py").read_text()
        self.assertIn('"default_title_model"', runtime_text)
        self.assertIn('"default_translate_image_model"', runtime_text)
        self.assertIn('"team_admin_count"', runtime_text)
        self.assertIn('"team_allowed_domain_count"', runtime_text)
        self.assertIn('"warnings"', runtime_text)
        self.assertIn('"ready_for_distributed_workers"', runtime_text)

    def test_personal_settings_page_uses_panel_and_auth(self):
        page_text = Path("apps/web/app/settings/personal/page.tsx").read_text()
        panel_text = Path("apps/web/components/personal-settings-panel.tsx").read_text()
        self.assertIn("requireSignedIn", page_text)
        self.assertIn("auth()", page_text)
        self.assertIn("PersonalSettingsPanel", page_text)
        self.assertIn("当前账号", panel_text)
        self.assertIn("默认标题模型", panel_text)
        self.assertIn("当前警告", panel_text)

    def test_team_settings_page_uses_panel_and_access(self):
        page_text = Path("apps/web/app/settings/team/page.tsx").read_text()
        panel_text = Path("apps/web/components/team-settings-panel.tsx").read_text()
        self.assertIn("TeamSettingsPanel", page_text)
        self.assertIn("getSessionAccess", page_text)
        self.assertIn("团队管理员配置", panel_text)
        self.assertIn("基础设施状态", panel_text)
        self.assertIn("团队部署警告", panel_text)


if __name__ == "__main__":
    unittest.main()
