from __future__ import annotations

from pathlib import Path
import unittest


class ZeaburTemplateTest(unittest.TestCase):
    def test_template_contains_expected_services_and_env(self):
        template_path = Path("template.yaml")
        self.assertTrue(template_path.exists())
        content = template_path.read_text()

        self.assertIn("apiVersion: zeabur.com/v1", content)
        self.assertIn("kind: Template", content)
        self.assertIn("- name: temu-app", content)
        self.assertIn("- name: postgresql", content)
        self.assertIn("- name: redis", content)
        self.assertIn("template: GIT", content)
        self.assertIn("repoID: 1184397680", content)
        self.assertIn("branch: main", content)
        self.assertIn(
            "DATABASE_URL:\n            default: ${POSTGRES_CONNECTION_STRING}",
            content,
        )
        self.assertIn(
            "REDIS_URL:\n            default: ${REDIS_CONNECTION_STRING}", content
        )
        self.assertIn('PLATFORM_AUTO_MIGRATE:\n            default: "true"', content)
        self.assertIn("TITLE_TEXT_MODEL:\n            default: gemini-3.1-pro", content)


if __name__ == "__main__":
    unittest.main()
