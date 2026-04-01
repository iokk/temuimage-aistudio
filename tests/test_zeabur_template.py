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
        self.assertIn("- name: web", content)
        self.assertIn("- name: api", content)
        self.assertIn("- name: worker", content)
        self.assertIn("- name: postgresql", content)
        self.assertIn("- name: redis", content)
        self.assertIn("template: GIT", content)
        self.assertIn("repoID: 1184397680", content)
        self.assertIn("branch: main", content)
        self.assertIn("dockerfile: apps/web/Dockerfile", content)
        self.assertIn("dockerfile: apps/api/Dockerfile", content)
        self.assertIn("dockerfile: apps/worker/Dockerfile", content)
        self.assertIn("CASDOOR_CLIENT_ID", content)
        self.assertIn("CASDOOR_CLIENT_SECRET", content)
        self.assertIn("CASDOOR_API_AUDIENCE", content)
        self.assertIn(
            "DATABASE_URL:\n            default: ${POSTGRES_CONNECTION_STRING}",
            content,
        )
        self.assertIn(
            "REDIS_URL:\n            default: ${REDIS_CONNECTION_STRING}", content
        )
        self.assertIn("JOB_STORE_BACKEND:\n            default: database", content)
        self.assertIn("ASYNC_JOB_BACKEND:\n            default: celery", content)
        self.assertIn('AUTO_BOOTSTRAP_DB:\n            default: "true"', content)
        self.assertIn('AUTO_BOOTSTRAP_DB:\n            default: "false"', content)
        self.assertIn("NEXTAUTH_SECRET", content)
        self.assertIn("CASDOOR_ISSUER", content)

    def test_service_dockerfiles_honor_runtime_port_defaults(self):
        api_dockerfile = Path("apps/api/Dockerfile").read_text()
        web_dockerfile = Path("apps/web/Dockerfile").read_text()

        self.assertIn("${PORT:-8000}", api_dockerfile)
        self.assertIn("${PORT:-3000}", web_dockerfile)


if __name__ == "__main__":
    unittest.main()
