from __future__ import annotations

from pathlib import Path
import unittest


class ApiSystemConfigTest(unittest.TestCase):
    def test_system_config_module_exists(self):
        text = Path("apps/api/core/system_config.py").read_text()
        self.assertIn("class SystemExecutionConfig", text)
        self.assertIn("def get_system_execution_config()", text)
        self.assertIn("def update_system_execution_config", text)
        self.assertIn('SYSTEM_EXECUTION_CONFIG_KEY = "system_execution"', text)

    def test_system_config_reads_expected_env_keys(self):
        text = Path("apps/api/core/system_config.py").read_text()
        self.assertIn('"TITLE_TEXT_MODEL"', text)
        self.assertIn('"TRANSLATE_PROVIDER"', text)
        self.assertIn('"TRANSLATE_IMAGE_MODEL"', text)
        self.assertIn('"TRANSLATE_ANALYSIS_MODEL"', text)
        self.assertIn('"QUICK_IMAGE_MODEL"', text)
        self.assertIn('"BATCH_IMAGE_MODEL"', text)
        self.assertIn('"RELAY_API_BASE"', text)
        self.assertIn('"RELAY_API_KEY"', text)
        self.assertIn('"GEMINI_API_KEY"', text)


if __name__ == "__main__":
    unittest.main()
