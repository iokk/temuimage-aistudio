from __future__ import annotations

import unittest

from temu_core.config_ui import build_login_tab_labels
from temu_core.runtime_mode import get_runtime_mode, should_show_team_features


class ModeRefactorTest(unittest.TestCase):
    def test_admin_tool_mode_hides_team_features(self):
        mode = get_runtime_mode(False, False)
        self.assertEqual(mode, "admin_tool_mode")
        self.assertFalse(should_show_team_features(mode))

    def test_team_mode_labels_are_two_mode_labels(self):
        labels = build_login_tab_labels("team_mode")
        self.assertEqual(labels, ["👤 个人模式", "🛠️ 团队/管理员"])


if __name__ == "__main__":
    unittest.main()
