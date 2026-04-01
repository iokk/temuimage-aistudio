from __future__ import annotations

from pathlib import Path
import unittest


class RebuildSchemaTest(unittest.TestCase):
    def test_prisma_schema_contains_core_models(self):
        schema = Path("packages/db/prisma/schema.prisma").read_text()
        for model_name in [
            "model User",
            "model Organization",
            "model Membership",
            "model Credential",
            "model Project",
            "model Job",
            "model SystemConfig",
        ]:
            self.assertIn(model_name, schema)

    def test_project_workspace_migration_exists(self):
        migration = Path(
            "packages/db/prisma/migrations/20260331_0003_add_project_workspace/migration.sql"
        ).read_text()
        self.assertIn('CREATE TABLE "Project"', migration)
        self.assertIn('ADD COLUMN "projectId" TEXT', migration)

    def test_membership_active_project_migration_exists(self):
        migration = Path(
            "packages/db/prisma/migrations/20260331_0004_add_active_project_to_membership/migration.sql"
        ).read_text()
        self.assertIn('ADD COLUMN "activeProjectId" TEXT', migration)
        self.assertIn(
            'FOREIGN KEY ("activeProjectId") REFERENCES "Project"("id")', migration
        )


if __name__ == "__main__":
    unittest.main()
