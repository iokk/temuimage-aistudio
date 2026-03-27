from __future__ import annotations

import unittest

from temu_core.task_center import (
    build_task_badge,
    build_task_panel_title,
    build_task_type_meta,
    count_pending_tasks,
)


class TaskCenterMetaTest(unittest.TestCase):
    def test_task_badge_shows_pending_count(self):
        badge = build_task_badge(2)
        self.assertTrue(badge["show"])
        self.assertIn("2", badge["label"])

    def test_task_badge_hidden_when_empty(self):
        badge = build_task_badge(0)
        self.assertFalse(badge["show"])

    def test_task_type_meta_maps_restore_page(self):
        meta = build_task_type_meta("smart_generation")
        self.assertEqual(meta["page"], "快速出图")
        self.assertIn("快速", meta["title"])

    def test_pending_task_count_ignores_completed(self):
        tasks = [
            {"status": "queued"},
            {"status": "running"},
            {"status": "completed"},
        ]
        self.assertEqual(count_pending_tasks(tasks), 2)

    def test_task_panel_title_uses_total_count(self):
        self.assertIn("3", build_task_panel_title(3))


if __name__ == "__main__":
    unittest.main()
