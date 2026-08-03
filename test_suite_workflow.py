import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

import app


class SuitePayloadTests(unittest.TestCase):
    def _plan(self):
        return {
            "target_count": 2,
            "assets": [
                {"id": "front-1", "path": "front-source.jpg", "role": "front"},
                {"id": "detail-1", "path": "detail-source.jpg", "role": "detail"},
                {"id": "side-1", "path": "side-source.jpg", "role": "side"},
            ],
            "plan_items": [
                {
                    "id": "plan-01",
                    "order": 1,
                    "type_key": "main-front",
                    "title": "Front hero",
                    "reference_asset_ids": ["front-1"],
                    "final_prompt": "Frozen front prompt",
                },
                {
                    "id": "plan-02",
                    "order": 2,
                    "type_key": "detail",
                    "title": "Material detail",
                    "reference_asset_ids": ["detail-1", "front-1", "side-1"],
                    "final_prompt": "Frozen detail prompt",
                },
            ],
        }

    def test_build_requests_freezes_plan_fields_and_selected_durable_paths(self):
        requests = app.build_suite_task_requests(
            self._plan(),
            [
                {"id": "front-1", "path": "/durable/front.png"},
                {"id": "detail-1", "path": "/durable/detail.png"},
                {"id": "side-1", "path": "/durable/side.png"},
            ],
        )

        self.assertEqual(
            requests,
            [
                {
                    "id": "plan-01",
                    "type_key": "main-front",
                    "type_name": "Front hero",
                    "title": "Front hero",
                    "final_prompt": "Frozen front prompt",
                    "reference_asset_ids": ["front-1"],
                    "image_paths": ["/durable/front.png"],
                },
                {
                    "id": "plan-02",
                    "type_key": "detail",
                    "type_name": "Material detail",
                    "title": "Material detail",
                    "final_prompt": "Frozen detail prompt",
                    "reference_asset_ids": ["detail-1", "front-1", "side-1"],
                    "image_paths": [
                        "/durable/detail.png",
                        "/durable/front.png",
                        "/durable/side.png",
                    ],
                },
            ],
        )

    def test_build_requests_accepts_id_to_path_mapping(self):
        request = app.build_suite_task_requests(
            {
                "plan_items": [
                    {
                        "id": "plan-01",
                        "type_key": "main-front",
                        "title": "Front hero",
                        "reference_asset_ids": ["front-1"],
                        "final_prompt": "Frozen front prompt",
                    }
                ]
            },
            {"front-1": Path("/durable/front.png")},
        )[0]

        self.assertEqual(request["image_paths"], ["/durable/front.png"])

    def test_build_requests_preserves_the_frozen_prompt_verbatim(self):
        plan = self._plan()
        plan["plan_items"] = [plan["plan_items"][0]]
        plan["plan_items"][0]["final_prompt"] = "  Frozen prompt\n"

        request = app.build_suite_task_requests(
            plan,
            {"front-1": "/durable/front.png"},
        )[0]

        self.assertEqual(request["final_prompt"], "  Frozen prompt\n")

    def test_build_requests_rejects_missing_reference_instead_of_using_all_assets(self):
        plan = self._plan()
        plan["plan_items"][0]["reference_asset_ids"] = ["missing-asset"]

        with self.assertRaisesRegex(ValueError, "missing-asset"):
            app.build_suite_task_requests(
                plan,
                {
                    "front-1": "/durable/front.png",
                    "detail-1": "/durable/detail.png",
                    "side-1": "/durable/side.png",
                },
            )

    def test_combo_validation_accepts_legacy_requests_and_checks_suite_requests(self):
        legacy_payload = {
            "image_paths": ["/durable/front.png"],
            "reqs": [{"type_name": "Main", "prompt": "legacy prompt"}],
        }
        suite_payload = {
            "suite_version": 1,
            "suite_draft": {},
            "suite_plan": self._plan(),
            "image_paths": [
                "/durable/front.png",
                "/durable/detail.png",
                "/durable/side.png",
            ],
            "reqs": app.build_suite_task_requests(
                self._plan(),
                {
                    "front-1": "/durable/front.png",
                    "detail-1": "/durable/detail.png",
                    "side-1": "/durable/side.png",
                },
            ),
        }

        self.assertEqual(app._validate_combo_task_payload(legacy_payload), [])
        self.assertEqual(app._validate_combo_task_payload(suite_payload), [])

        suite_payload["reqs"][0]["image_paths"] = []
        errors = app._validate_combo_task_payload(suite_payload)
        self.assertTrue(any("参考图" in error for error in errors))

    def test_consume_request_persists_the_approved_suite_snapshot(self):
        suite_plan = {
            "target_count": 1,
            "assets": [
                {"id": "front-1", "path": "session-only.png", "role": "front"}
            ],
            "plan_items": [
                {
                    "id": "plan-01",
                    "order": 1,
                    "type_key": "main-front",
                    "title": "Front hero",
                    "reference_asset_ids": ["front-1"],
                    "final_prompt": "Frozen front prompt",
                }
            ],
        }
        suite_draft = {
            "target_count": 1,
            "target_language": "English",
            "assets": copy.deepcopy(suite_plan["assets"]),
            "selected_type_counts": {"main-front": 1},
        }
        state = {
            "combo_generating": True,
            "combo_images": [Image.new("RGB", (8, 8), "white")],
            "combo_reqs": [{"type_name": "stale legacy request"}],
            "combo_anchor": {"category": "mug"},
            "combo_suite_draft": suite_draft,
            "combo_suite_plan": suite_plan,
            "combo_image_language": "en",
            "combo_enable_title": False,
            "combo_title_info": "",
        }
        provider = {
            "id": "provider-1",
            "title_model": "gpt-4o-mini",
            "vision_model": "gpt-4o-mini",
        }

        with (
            tempfile.TemporaryDirectory() as temporary_directory,
            patch.object(app, "DATA_DIR", Path(temporary_directory)),
            patch.object(
                app,
                "create_task",
                return_value=({"id": "suite-task"}, ""),
            ) as create_task,
        ):
            result = app.consume_combo_generation_request(
                provider, "fallback-model", state=state
            )
            payload = create_task.call_args.args[1]
            self.assertEqual(len(payload["image_paths"]), 1)
            self.assertTrue(Path(payload["image_paths"][0]).is_file())

        suite_plan["plan_items"][0]["final_prompt"] = "session drift"
        suite_draft["target_language"] = "session drift"

        self.assertEqual(result, ({"id": "suite-task"}, ""))
        self.assertEqual(payload["suite_version"], 1)
        self.assertEqual(payload["suite_draft"]["target_language"], "English")
        self.assertEqual(
            payload["suite_plan"]["plan_items"][0]["final_prompt"],
            "Frozen front prompt",
        )
        self.assertEqual(payload["reqs"][0]["id"], "plan-01")
        self.assertEqual(payload["reqs"][0]["final_prompt"], "Frozen front prompt")
        self.assertEqual(payload["reqs"][0]["image_paths"], payload["image_paths"])
        self.assertFalse(state["combo_generating"])


if __name__ == "__main__":
    unittest.main()
