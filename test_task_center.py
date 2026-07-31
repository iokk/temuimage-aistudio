import unittest
from unittest.mock import Mock, patch

import app


class TaskCenterItemViewTests(unittest.TestCase):
    def test_task_center_actions_cover_every_lifecycle_state(self):
        cases = [
            (None, "empty", False, False),
            ({"status": "queued", "type": "smart"}, "queued", True, False),
            ({"status": "running", "type": "smart"}, "running", True, False),
            ({"status": "done", "type": "smart"}, "done", False, False),
            ({"status": "partial", "type": "smart"}, "partial", False, False),
            ({"status": "error", "type": "smart"}, "error", False, False),
            ({"status": "cancelled", "type": "smart"}, "cancelled", False, False),
            ({"status": "expired", "type": "smart"}, "expired", False, False),
            (
                {
                    "status": "partial",
                    "type": "smart",
                    "item_results": [
                        {
                            "status": "error",
                            "prompt": "retry transient item",
                            "retryable": True,
                        }
                    ],
                },
                "partial",
                False,
                True,
            ),
        ]

        for task, status, can_cancel, can_retry in cases:
            with self.subTest(status=status, can_retry=can_retry):
                state = app.build_task_center_state(task)
                self.assertEqual(state["status"], status)
                self.assertEqual(state["can_cancel"], can_cancel)
                self.assertEqual(state["can_retry_failed_items"], can_retry)

    def test_task_error_summary_sanitizes_stored_values(self):
        summary = app.format_task_error_summary(
            ["<b>Authorization: Bearer token-123 sk-hidden-token-123</b>"],
            limit=1,
        )

        self.assertNotIn("<b>", summary)
        self.assertNotIn("Bearer", summary)
        self.assertNotIn("sk-hidden-token-123", summary)
    def test_mixed_results_are_ordered_and_missing_items_are_pending(self):
        task = {
            "status": "running",
            "progress": {"done": 2, "total": 3},
            "item_results": [
                {
                    "index": 2,
                    "type_name": "详情图",
                    "status": "error",
                    "error": "upstream timeout",
                },
                {
                    "index": 1,
                    "type_name": "主图",
                    "status": "done",
                    "file_path": "/tmp/main.png",
                },
            ],
        }

        views = app.build_task_item_views(task)

        self.assertEqual(
            views,
            [
                {
                    "index": 1,
                    "label": "主图",
                    "status": "done",
                    "file_path": "/tmp/main.png",
                    "error": "",
                },
                {
                    "index": 2,
                    "label": "详情图",
                    "status": "error",
                    "file_path": "",
                    "error": "upstream timeout",
                },
                {
                    "index": 3,
                    "label": "第 3 项",
                    "status": "pending",
                    "file_path": "",
                    "error": "",
                },
            ],
        )

    def test_legacy_result_files_are_exposed_as_successful_items(self):
        task = {
            "status": "done",
            "result_files": ["/tmp/first.png", "/tmp/second.png"],
        }

        views = app.build_task_item_views(task)

        self.assertEqual(
            [(view["label"], view["status"], view["file_path"]) for view in views],
            [
                ("图片 1", "done", "/tmp/first.png"),
                ("图片 2", "done", "/tmp/second.png"),
            ],
        )

    def test_unsupported_tasks_do_not_offer_failed_item_retry(self):
        task = {
            "type": "text_to_image",
            "item_results": [{"status": "error", "prompt": "retry me"}],
        }

        self.assertFalse(app.has_retryable_failed_items(task))

    def test_combo_retryable_item_count_uses_recoverable_requests(self):
        task = {
            "type": "combo",
            "status": "partial",
            "payload": {
                "reqs": [
                    {"type_name": "主图白底"},
                    {"type_name": "功能卖点图"},
                ]
            },
            "item_results": [
                {
                    "index": 1,
                    "status": "done",
                    "type_name": "主图白底",
                    "file_path": "done.png",
                },
                {
                    "index": 2,
                    "status": "error",
                    "type_name": "功能卖点图",
                    "error": "请求超时，请检查网络、代理或模型响应速度。",
                },
            ],
        }

        retryable_items = app.get_retryable_failed_items(task)

        self.assertEqual(len(retryable_items), 1)
        self.assertEqual(retryable_items[0]["index"], 2)

    def test_retry_child_with_original_batch_index_has_one_item_view(self):
        task = {
            "type": "combo",
            "status": "partial",
            "progress": {"done": 1, "total": 1},
            "item_results": [
                {
                    "index": 2,
                    "type_name": "功能卖点图",
                    "status": "error",
                    "error": "请求超时，请检查网络、代理或模型响应速度。",
                }
            ],
        }

        self.assertEqual(
            app.build_task_item_views(task),
            [
                {
                    "index": 1,
                    "label": "功能卖点图",
                    "status": "error",
                    "file_path": "",
                    "error": "请求超时，请检查网络、代理或模型响应速度。",
                }
            ],
        )

    def test_retry_child_summary_uses_child_total(self):
        task = {
            "summary": "重试失败项 · 智能组图任务 · 2张",
            "payload": {
                "retry_parent_id": "parent-task",
                "total": 1,
            },
            "progress": {"done": 1, "total": 1},
        }

        self.assertEqual(
            app.build_task_display_summary(task),
            "重试失败项 · 智能组图任务 · 1张",
        )

    def test_renderer_uses_four_columns_and_full_width_images(self):
        active_columns = []

        class Column:
            def __init__(self):
                self.entered = False

            def __enter__(self):
                self.entered = True
                active_columns.append(self)
                return self

            def __exit__(self, exc_type, exc_value, traceback):
                active_columns.pop()
                return False

        columns = [Column() for _ in range(4)]
        streamlit = Mock()
        streamlit.columns.return_value = columns
        image_columns = []
        streamlit.image.side_effect = lambda *args, **kwargs: image_columns.append(
            active_columns[-1]
        )
        task = {
            "status": "done",
            "item_results": [
                {
                    "index": 1,
                    "type_name": "主图",
                    "status": "done",
                    "file_path": "/tmp/success.png",
                }
            ],
        }

        with (
            patch.object(app, "st", streamlit),
            patch.object(app.Path, "exists", return_value=True),
        ):
            app.render_task_item_results(task, show_images=True)

        streamlit.columns.assert_called_once_with(4)
        self.assertTrue(columns[0].entered)
        self.assertEqual(image_columns, [columns[0]])
        streamlit.image.assert_called_once_with(
            "/tmp/success.png",
            caption="成功 · 主图",
            width="stretch",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
