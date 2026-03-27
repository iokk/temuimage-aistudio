from __future__ import annotations

import unittest

from temu_core.runtime_mode import (
    get_runtime_mode,
    should_show_team_features,
    should_force_registered_login,
)


class RuntimeModeTest(unittest.TestCase):
    def test_missing_database_uses_admin_tool_mode(self):
        self.assertEqual(get_runtime_mode(False, False), "admin_tool_mode")
        self.assertFalse(should_show_team_features("admin_tool_mode"))

    def test_database_ready_uses_team_mode(self):
        self.assertEqual(get_runtime_mode(True, True), "team_mode")
        self.assertTrue(should_show_team_features("team_mode"))

    def test_force_registered_login_only_in_team_mode(self):
        self.assertFalse(
            should_force_registered_login(
                runtime_mode="admin_tool_mode",
                is_admin=False,
                use_own_key=False,
                has_auth_user_id=False,
            )
        )
        self.assertTrue(
            should_force_registered_login(
                runtime_mode="team_mode",
                is_admin=False,
                use_own_key=False,
                has_auth_user_id=False,
            )
        )


if __name__ == "__main__":
    unittest.main()
