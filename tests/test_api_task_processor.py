from __future__ import annotations

from pathlib import Path
import unittest


class ApiTaskProcessorRecoveryTest(unittest.TestCase):
    def test_task_processor_routes_title_to_real_execution(self):
        processor_text = Path("apps/api/task_processor.py").read_text()
        execution_text = Path("apps/api/task_execution.py").read_text()
        self.assertIn(
            "from apps.api.task_execution import execute_title_task", processor_text
        )
        self.assertIn("return execute_title_task(payload)", processor_text)
        self.assertIn("generate_compliant_titles_or_raise", execution_text)
        self.assertIn('source": "execution"', execution_text)
        self.assertIn('"execution_context"', execution_text)

    def test_title_workspace_no_longer_describes_preview_flow(self):
        workspace_text = Path("apps/web/components/title-workspace.tsx").read_text()
        self.assertIn("生成标题", workspace_text)
        self.assertIn("真实标题任务", workspace_text)
        self.assertIn("timeoutMs: 45000", workspace_text)


if __name__ == "__main__":
    unittest.main()
