"""自动刷新逻辑的 mock 测试：不依赖真实 Streamlit 运行时与 API 凭据。"""
import unittest
from unittest.mock import patch

import app


class CountActiveTasksTest(unittest.TestCase):
    def test_counts_only_unfinished(self):
        tasks = [
            {"status": "queued"},
            {"status": "running"},
            {"status": "done"},
            {"status": "failed"},
            {"status": "cancelled"},
        ]
        with patch.object(app, "list_tasks_for_display", return_value=tasks):
            self.assertEqual(app.count_active_tasks_for_display(), 2)

    def test_empty_is_zero(self):
        with patch.object(app, "list_tasks_for_display", return_value=[]):
            self.assertEqual(app.count_active_tasks_for_display(), 0)

    def test_missing_status_is_not_active(self):
        with patch.object(app, "list_tasks_for_display", return_value=[{}]):
            self.assertEqual(app.count_active_tasks_for_display(), 0)

    def test_storage_failure_degrades_to_zero(self):
        """存储层异常不能让页面陷入刷新循环。"""
        with patch.object(
            app, "list_tasks_for_display", side_effect=RuntimeError("db down")
        ):
            self.assertEqual(app.count_active_tasks_for_display(), 0)


class MaybeAutoRefreshTest(unittest.TestCase):
    def test_reruns_while_active(self):
        with patch.object(app, "count_active_tasks_for_display", return_value=1), \
             patch.object(app.st, "session_state", {"auto_refresh_tasks": True}), \
             patch.object(app.time, "sleep") as sleep, \
             patch.object(app.st, "rerun") as rerun:
            app.maybe_auto_refresh_for_tasks()
            sleep.assert_called_once_with(app.AUTO_REFRESH_SECONDS)
            rerun.assert_called_once()

    def test_idle_page_does_not_loop(self):
        with patch.object(app, "count_active_tasks_for_display", return_value=0), \
             patch.object(app.st, "session_state", {"auto_refresh_tasks": True}), \
             patch.object(app.time, "sleep") as sleep, \
             patch.object(app.st, "rerun") as rerun:
            app.maybe_auto_refresh_for_tasks()
            sleep.assert_not_called()
            rerun.assert_not_called()

    def test_opt_out_respected_even_with_active_tasks(self):
        with patch.object(app, "count_active_tasks_for_display", return_value=3), \
             patch.object(app.st, "session_state", {"auto_refresh_tasks": False}), \
             patch.object(app.time, "sleep") as sleep, \
             patch.object(app.st, "rerun") as rerun:
            app.maybe_auto_refresh_for_tasks()
            sleep.assert_not_called()
            rerun.assert_not_called()

    def test_defaults_to_on_when_unset(self):
        with patch.object(app, "count_active_tasks_for_display", return_value=1), \
             patch.object(app.st, "session_state", {}), \
             patch.object(app.time, "sleep"), \
             patch.object(app.st, "rerun") as rerun:
            app.maybe_auto_refresh_for_tasks()
            rerun.assert_called_once()


class TitleCharRangeTest(unittest.TestCase):
    def test_chinese_range_is_separate(self):
        self.assertEqual(app.get_title_char_range("zh"), (40, 80))

    def test_latin_languages_share_range(self):
        self.assertEqual(app.get_title_char_range("es"), (150, 200))
        self.assertEqual(app.get_title_char_range("fr"), (150, 200))

    def test_unknown_language_falls_back(self):
        self.assertEqual(
            app.get_title_char_range("de"),
            (app.TRI_TITLE_MIN_CHARS, app.TRI_TITLE_MAX_CHARS),
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
