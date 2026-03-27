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
            "model Job",
            "model SystemConfig",
        ]:
            self.assertIn(model_name, schema)


if __name__ == "__main__":
    unittest.main()
