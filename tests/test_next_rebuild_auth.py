from __future__ import annotations

import json
from pathlib import Path
import unittest


class NextRebuildAuthTest(unittest.TestCase):
    def test_web_package_declares_next_auth(self):
        package_json = json.loads(Path("apps/web/package.json").read_text())
        deps = package_json.get("dependencies", {})
        self.assertIn("next-auth", deps)

    def test_auth_files_exist(self):
        self.assertTrue(Path("apps/web/auth.ts").exists())
        self.assertTrue(Path("apps/web/auth.config.ts").exists())
        self.assertTrue(Path("apps/web/app/api/auth/[...nextauth]/route.ts").exists())
        self.assertTrue(Path("apps/web/app/login/page.tsx").exists())
        self.assertTrue(Path("apps/web/app/actions/auth-actions.ts").exists())
        self.assertTrue(Path("apps/web/middleware.ts").exists())
        self.assertTrue(Path("apps/web/lib/access.ts").exists())
        self.assertTrue(Path("apps/web/lib/guards.ts").exists())

    def test_rebuild_env_template_contains_casdoor_keys(self):
        env_text = Path(".env.rebuild.example").read_text()
        for key in [
            "CASDOOR_ISSUER",
            "CASDOOR_CLIENT_ID",
            "CASDOOR_CLIENT_SECRET",
            "TEAM_ADMIN_EMAILS",
            "TEAM_ALLOWED_EMAIL_DOMAINS",
            "NEXTAUTH_SECRET",
            "NEXTAUTH_URL",
        ]:
            self.assertIn(key, env_text)

    def test_login_page_mentions_personal_and_team_modes(self):
        login_page = Path("apps/web/app/login/page.tsx").read_text()
        self.assertIn("个人模式", login_page)
        self.assertIn("团队模式", login_page)
        self.assertIn("signInWithCasdoor", login_page)

    def test_app_shell_contains_footer_branding(self):
        shell = Path("apps/web/components/app-shell.tsx").read_text()
        self.assertIn("深圳祖尔科技有限公司", shell)
        self.assertIn("rebuild-v1.0.0", shell)

    def test_protected_pages_use_guards(self):
        tasks_page = Path("apps/web/app/tasks/page.tsx").read_text()
        self.assertIn("requireSignedIn", tasks_page)

        team_page = Path("apps/web/app/settings/team/page.tsx").read_text()
        self.assertIn("requireTeamMember", team_page)

        admin_page = Path("apps/web/app/admin/page.tsx").read_text()
        self.assertIn("requireAdmin", admin_page)

    def test_middleware_protects_settings_tasks_and_admin(self):
        middleware = Path("apps/web/middleware.ts").read_text()
        self.assertIn('"/tasks/:path*"', middleware)
        self.assertIn('"/settings/:path*"', middleware)
        self.assertIn('"/admin/:path*"', middleware)
        self.assertIn("TEAM_ADMIN_EMAILS", Path(".env.rebuild.example").read_text())


if __name__ == "__main__":
    unittest.main()
