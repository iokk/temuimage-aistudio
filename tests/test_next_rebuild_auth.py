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
        self.assertTrue(Path("apps/web/app/api/auth/[...nextauth]/route.ts").exists())
        self.assertTrue(Path("apps/web/app/login/page.tsx").exists())

    def test_rebuild_env_template_contains_casdoor_keys(self):
        env_text = Path(".env.rebuild.example").read_text()
        for key in [
            "CASDOOR_ISSUER",
            "CASDOOR_CLIENT_ID",
            "CASDOOR_CLIENT_SECRET",
            "NEXTAUTH_SECRET",
            "NEXTAUTH_URL",
        ]:
            self.assertIn(key, env_text)


if __name__ == "__main__":
    unittest.main()
