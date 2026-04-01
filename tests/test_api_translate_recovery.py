from __future__ import annotations

from pathlib import Path
import unittest


class ApiTranslateRecoveryTest(unittest.TestCase):
    def test_task_processor_routes_translate_to_real_execution(self):
        processor_text = Path("apps/api/task_processor.py").read_text()
        execution_text = Path("apps/api/task_execution.py").read_text()
        self.assertIn(
            "from apps.api.task_execution import execute_translate_task", processor_text
        )
        self.assertIn("return execute_translate_task(payload)", processor_text)
        self.assertIn("def execute_translate_task", execution_text)
        self.assertIn('"execution_mode": "text"', execution_text)
        self.assertIn('"execution_mode": "image_batch"', execution_text)
        self.assertIn('"artifact_data_url"', execution_text)
        self.assertIn('"outputs"', execution_text)


if __name__ == "__main__":
    unittest.main()
