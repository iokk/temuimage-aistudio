from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import unittest


class GenerateZeaburEnvTest(unittest.TestCase):
    def run_script(self, *extra_args: str) -> str:
        script_path = Path("scripts/generate_zeabur_env.py")
        command = [
            sys.executable,
            str(script_path),
            "--web-domain",
            "studio.example.com",
            "--api-domain",
            "api.example.com",
            "--casdoor-issuer",
            "https://casdoor.example.com",
            "--casdoor-client-id",
            "client-id",
            "--casdoor-client-secret",
            "client-secret",
            "--admin-emails",
            "owner@example.com",
            "--allowed-domains",
            "example.com",
            "--nextauth-secret",
            "fixed-nextauth-secret",
            "--system-encryption-key",
            "fixed-system-key",
            *extra_args,
        ]
        completed = subprocess.run(command, check=True, capture_output=True, text=True)
        return completed.stdout

    def test_all_format_contains_template_and_service_sections(self):
        output = self.run_script()

        self.assertIn("# Zeabur template variables", output)
        self.assertIn("WEB_DOMAIN=studio.example.com", output)
        self.assertIn("API_DOMAIN=api.example.com", output)
        self.assertIn("[web]", output)
        self.assertIn("NEXT_PUBLIC_API_BASE_URL=https://api.example.com", output)
        self.assertIn("[api]", output)
        self.assertIn("DATABASE_URL=${POSTGRES_CONNECTION_STRING}", output)
        self.assertIn("AUTO_BOOTSTRAP_DB=true", output)
        self.assertIn("[worker]", output)
        self.assertIn("AUTO_BOOTSTRAP_DB=false", output)

    def test_template_only_format_omits_service_sections(self):
        output = self.run_script("--format", "template")

        self.assertIn("# Zeabur template variables", output)
        self.assertNotIn("[web]", output)
        self.assertNotIn("[api]", output)

    def test_services_only_format_omits_template_header(self):
        output = self.run_script("--format", "services")

        self.assertNotIn("# Zeabur template variables", output)
        self.assertIn("# Service env blocks", output)
        self.assertIn("NEXTAUTH_URL=https://studio.example.com", output)
        self.assertIn("SYSTEM_ENCRYPTION_KEY=fixed-system-key", output)


if __name__ == "__main__":
    unittest.main()
