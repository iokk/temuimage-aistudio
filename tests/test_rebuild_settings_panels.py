from __future__ import annotations

from pathlib import Path
import unittest


class RebuildSettingsPanelsTest(unittest.TestCase):
    def test_runtime_payload_includes_account_team_state_types(self):
        runtime_text = Path("apps/web/lib/runtime.ts").read_text()
        self.assertIn("current_user", runtime_text)
        self.assertIn("current_team", runtime_text)
        self.assertIn("current_project", runtime_text)
        self.assertIn("membership_role", runtime_text)

    def test_personal_settings_panel_renders_persisted_account_state(self):
        panel_text = Path("apps/web/components/personal-settings-panel.tsx").read_text()
        config_panel_text = Path(
            "apps/web/components/personal-config-panel.tsx"
        ).read_text()
        self.assertIn("持久化账号状态", panel_text)
        self.assertIn("runtime?.current_user?.issuer", panel_text)
        self.assertIn("runtime?.current_user?.subject", panel_text)
        self.assertIn("runtime?.current_user?.last_login_at", panel_text)
        self.assertIn("PersonalConfigPanel", panel_text)
        self.assertIn("getServerPersonalExecutionConfig", panel_text)
        self.assertIn("当前个人执行配置", config_panel_text)
        self.assertIn("Personal Workspace", config_panel_text)

    def test_team_settings_panel_renders_persisted_team_state(self):
        panel_text = Path("apps/web/components/team-settings-panel.tsx").read_text()
        self.assertIn("当前团队状态", panel_text)
        self.assertIn("CurrentProjectPanel", panel_text)
        self.assertIn("runtime?.current_team?.organization_name", panel_text)
        self.assertIn("runtime?.current_team?.organization_slug", panel_text)
        self.assertIn("runtime?.current_team?.membership_role", panel_text)
        self.assertIn(
            "默认项目管理：请在下方项目管理卡片中维护当前项目名称。", panel_text
        )

    def test_current_project_panel_exists_with_management_ui(self):
        panel_text = Path("apps/web/components/current-project-panel.tsx").read_text()
        self.assertIn("当前项目管理", panel_text)
        self.assertIn("保存当前项目", panel_text)
        self.assertIn("创建并切换项目", panel_text)
        self.assertIn("/api/platform/projects", panel_text)
        self.assertIn("/api/platform/projects/current/select", panel_text)
        self.assertIn("/api/platform/projects/current", panel_text)


if __name__ == "__main__":
    unittest.main()
