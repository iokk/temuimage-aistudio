from __future__ import annotations

from pathlib import Path
import json
import unittest


class RebuildDeployReadyTest(unittest.TestCase):
    def test_db_package_has_deploy_and_seed_scripts(self):
        package_json = json.loads(Path("packages/db/package.json").read_text())
        scripts = package_json.get("scripts", {})
        self.assertIn("validate", scripts)
        self.assertIn("migrate:deploy", scripts)
        self.assertIn("seed:system", scripts)
        self.assertIn("deploy:v1", scripts)

    def test_root_package_has_db_deploy_script(self):
        package_json = json.loads(Path("package.json").read_text())
        scripts = package_json.get("scripts", {})
        self.assertIn("deploy:db", scripts)
        self.assertIn("prisma:validate", scripts)
        self.assertIn("prisma:migrate:deploy", scripts)

    def test_prisma_migration_and_seed_exist(self):
        self.assertTrue(
            Path(
                "packages/db/prisma/migrations/20260328_0001_init_rebuild_schema/migration.sql"
            ).exists()
        )
        seed_text = Path("packages/db/scripts/bootstrap-system-user.mjs").read_text()
        self.assertIn("system@xiaobaitu.local", seed_text)
        self.assertIn("upsert", seed_text)

    def test_rebuild_compose_includes_postgres_redis_api_worker_web(self):
        compose_text = Path("docker-compose.rebuild.yml").read_text()
        for name in ["postgres:", "redis:", "api:", "worker:", "web:"]:
            self.assertIn(name, compose_text)
        self.assertIn("JOB_STORE_BACKEND: database", compose_text)
        self.assertIn("ASYNC_JOB_BACKEND: celery", compose_text)

    def test_release_smoke_script_and_runbook_exist(self):
        smoke_text = Path("scripts/rebuild_release_smoke.py").read_text()
        runbook_text = Path("docs/rebuild-v1-deploy-runbook.md").read_text()
        env_text = Path(".env.rebuild.production.example").read_text()
        package_json = json.loads(Path("package.json").read_text())
        scripts = package_json.get("scripts", {})
        self.assertIn("/v1/system/readiness", smoke_text)
        self.assertIn("--require-ready", smoke_text)
        self.assertIn("release:smoke", scripts)
        self.assertIn("Readiness", runbook_text)
        self.assertIn("ASYNC_JOB_BACKEND=celery", env_text)

    def test_zeabur_specific_release_support_exists(self):
        zeabur_env = Path(".env.zeabur.production.example").read_text()
        zeabur_doc = Path("docs/zeabur-rebuild-v1.md").read_text()
        zeabur_script = Path("scripts/zeabur_rebuild_release.sh").read_text()
        fill_template = Path("docs/zeabur-console-fill-template.md").read_text()
        generator_script = Path("scripts/generate_zeabur_env.py").read_text()
        self.assertIn("NEXT_PUBLIC_API_BASE_URL", zeabur_env)
        self.assertIn("apps/api/Dockerfile", zeabur_doc)
        self.assertIn("apps/worker/Dockerfile", zeabur_doc)
        self.assertIn("pnpm deploy:db", zeabur_script)
        self.assertIn("--require-ready", zeabur_script)
        self.assertIn("WEB_DOMAIN", fill_template)
        self.assertIn("Zeabur 控制台逐项填写模板", fill_template)
        self.assertIn("NEXTAUTH_SECRET", generator_script)
        self.assertIn("SYSTEM_ENCRYPTION_KEY", generator_script)


if __name__ == "__main__":
    unittest.main()
