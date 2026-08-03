import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

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

    def _suite_payload(self):
        return {
            "suite_version": 1,
            "suite_draft": {},
            "suite_plan": self._plan(),
            "image_paths": [
                "/durable/front.png",
                "/durable/detail.png",
                "/durable/side.png",
            ],
            "reqs": [
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
        suite_payload = self._suite_payload()

        self.assertEqual(app._validate_combo_task_payload(legacy_payload), [])
        self.assertEqual(app._validate_combo_task_payload(suite_payload), [])

        suite_payload["reqs"][0]["image_paths"] = []
        errors = app._validate_combo_task_payload(suite_payload)
        self.assertTrue(any("参考图" in error for error in errors))

    def test_snapshot_validation_rejects_requests_that_drift_from_the_plan(self):
        for field, drifted_value in (
            ("id", "plan-99"),
            ("type_key", "scene"),
            ("title", "Drifted title"),
            ("type_name", "Drifted display title"),
            ("final_prompt", "Drifted prompt"),
        ):
            with self.subTest(field=field):
                payload = self._suite_payload()
                payload["reqs"][0][field] = drifted_value

                errors = app._validate_combo_task_payload(payload)

                self.assertTrue(any("冻结计划不一致" in error for error in errors))

        payload = self._suite_payload()
        payload["reqs"][0]["reference_asset_ids"] = ["detail-1"]
        payload["reqs"][0]["image_paths"] = ["/durable/detail.png"]

        errors = app._validate_combo_task_payload(payload)

        self.assertTrue(any("冻结计划不一致" in error for error in errors))

    def test_snapshot_validation_rejects_empty_or_duplicate_reference_ids(self):
        for reference_ids, image_paths in (
            ([""], ["/durable/front.png"]),
            (
                ["front-1", "front-1"],
                ["/durable/front.png", "/durable/front.png"],
            ),
        ):
            with self.subTest(reference_ids=reference_ids):
                payload = self._suite_payload()
                payload["reqs"][0]["reference_asset_ids"] = reference_ids
                payload["reqs"][0]["image_paths"] = image_paths

                errors = app._validate_combo_task_payload(payload)

                self.assertTrue(any("引用素材 ID" in error for error in errors))

    def test_snapshot_validation_rejects_unknown_assets(self):
        payload = self._suite_payload()
        payload["reqs"][0]["reference_asset_ids"] = ["unknown-asset"]

        errors = app._validate_combo_task_payload(payload)

        self.assertTrue(any("未知素材" in error for error in errors))

    def test_snapshot_validation_rejects_conflicting_asset_path_mappings(self):
        payload = self._suite_payload()
        payload["image_paths"].append("/durable/conflicting-front.png")
        payload["reqs"][1]["image_paths"][1] = "/durable/conflicting-front.png"

        errors = app._validate_combo_task_payload(payload)

        self.assertTrue(any("映射冲突" in error for error in errors))

    def test_snapshot_validation_rejects_different_assets_sharing_one_path(self):
        payload = self._suite_payload()
        payload["reqs"][1]["image_paths"][0] = "/durable/front.png"

        errors = app._validate_combo_task_payload(payload)

        self.assertTrue(any("路径重复映射" in error for error in errors))

    def test_snapshot_validation_enforces_request_identity_sets_and_retry_subsets(self):
        missing_request = self._suite_payload()
        missing_request["reqs"] = missing_request["reqs"][:1]
        duplicate_request = self._suite_payload()
        duplicate_request["reqs"][1]["id"] = "plan-01"

        missing_errors = app._validate_combo_task_payload(missing_request)
        duplicate_errors = app._validate_combo_task_payload(duplicate_request)

        self.assertTrue(any("完整匹配" in error for error in missing_errors))
        self.assertTrue(any("请求 ID 重复" in error for error in duplicate_errors))

        retry_payload = self._suite_payload()
        retry_payload["retry_parent_id"] = "parent-task"
        retry_payload["reqs"] = retry_payload["reqs"][1:]
        self.assertEqual(app._validate_combo_task_payload(retry_payload), [])

    def test_snapshot_validation_requires_valid_unique_plan_records(self):
        invalid_assets = self._suite_payload()
        invalid_assets["suite_plan"]["assets"] = {}
        duplicate_asset = self._suite_payload()
        duplicate_asset["suite_plan"]["assets"][1]["id"] = "front-1"
        invalid_items = self._suite_payload()
        invalid_items["suite_plan"]["plan_items"] = {}
        duplicate_item = self._suite_payload()
        duplicate_item["suite_plan"]["plan_items"][1]["id"] = "plan-01"

        self.assertTrue(
            any(
                "assets 必须是有效列表" in error
                for error in app._validate_combo_task_payload(invalid_assets)
            )
        )
        self.assertTrue(
            any(
                "素材 ID 重复" in error
                for error in app._validate_combo_task_payload(duplicate_asset)
            )
        )
        self.assertTrue(
            any(
                "plan_items 必须是有效列表" in error
                for error in app._validate_combo_task_payload(invalid_items)
            )
        )
        self.assertTrue(
            any(
                "计划项 ID 重复" in error
                for error in app._validate_combo_task_payload(duplicate_item)
            )
        )

    def test_snapshot_validation_requires_requests_to_be_a_nonempty_list(self):
        payload = self._suite_payload()
        payload["reqs"] = {"plan-01": payload["reqs"][0]}

        errors = app._validate_combo_task_payload(payload)

        self.assertTrue(any("reqs 必须是非空列表" in error for error in errors))

    def test_snapshot_validation_rejects_non_string_request_ids_without_crashing(self):
        payload = self._suite_payload()
        payload["reqs"][0]["id"] = ["plan-01"]

        errors = app._validate_combo_task_payload(payload)

        self.assertTrue(any("缺少有效 ID" in error for error in errors))

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


class SuiteExecutionTests(unittest.TestCase):
    def _request(
        self,
        item_id,
        type_key,
        title,
        prompt,
        reference_ids,
        image_paths,
    ):
        return {
            "id": item_id,
            "type_key": type_key,
            "type_name": title,
            "title": title,
            "final_prompt": prompt,
            "reference_asset_ids": reference_ids,
            "image_paths": image_paths,
        }

    def _execution(self, reqs):
        execution = Mock()
        execution.task = {
            "id": "suite-execution",
            "type": "combo",
            "payload": {
                "suite_version": app.SUITE_TASK_VERSION,
                "provider_id": "provider-1",
                "image_paths": ["front.png", "detail.png", "side.png"],
                "reqs": reqs,
                "aspect": "1:1",
                "size": "1K",
                "thinking_level": "high",
                "image_language": "en",
            },
        }
        return execution

    def test_executes_frozen_requests_with_only_selected_references_and_normalizes_outputs(self):
        reqs = [
            self._request(
                "plan-01",
                "main-front",
                "Front hero",
                "Frozen front prompt",
                ["front-1"],
                ["front.png"],
            ),
            self._request(
                "plan-02",
                "detail",
                "Material detail",
                "Frozen detail prompt",
                ["detail-1", "side-1"],
                ["detail.png", "side.png"],
            ),
        ]
        original_reqs = copy.deepcopy(reqs)
        execution = self._execution(reqs)
        loaded_references = {
            ("front.png",): ["front-ref"],
            ("detail.png", "side.png"): ["detail-ref", "side-ref"],
        }
        generated_calls = []

        class FrozenPromptClient:
            last_error = ""

            def compose_image_prompt(self, *_args):
                raise AssertionError("suite execution must not recompose frozen prompts")

            def generate_image(self, references, prompt, *args):
                generated_calls.append((list(references), prompt))
                return f"generated-{len(generated_calls)}"

            def get_last_error(self):
                return self.last_error

        normalized_outputs = [
            {
                "path": "/results/suite-execution_01.jpg",
                "format": "JPEG",
                "width": 1600,
                "height": 1600,
                "bytes": 120000,
                "dpi": (72, 72),
            },
            {
                "path": "/results/suite-execution_02.png",
                "format": "PNG",
                "width": 1600,
                "height": 1600,
                "bytes": 220000,
                "dpi": (72, 72),
            },
        ]

        with (
            patch.object(
                app,
                "get_provider_by_id",
                return_value={"id": "provider-1", "api_key": "test-key"},
            ),
            patch.object(app, "get_active_provider", return_value=None),
            patch.object(
                app,
                "load_image_paths",
                side_effect=lambda paths: loaded_references[tuple(paths)],
            ) as load_images,
            patch.object(app, "create_ai_client", return_value=FrozenPromptClient()),
            patch.object(
                app,
                "normalize_suite_image",
                side_effect=normalized_outputs,
            ) as normalize_image,
        ):
            result = app._execute_combo_task(execution)

        self.assertEqual(
            [call.args[0] for call in load_images.call_args_list],
            [["front.png"], ["detail.png", "side.png"]],
        )
        self.assertEqual(
            generated_calls,
            [
                (["front-ref"], "Frozen front prompt"),
                (["detail-ref", "side-ref"], "Frozen detail prompt"),
            ],
        )
        self.assertEqual(normalize_image.call_count, 2)
        self.assertEqual(result["files"], [output["path"] for output in normalized_outputs])
        self.assertFalse(result["partial"])
        self.assertEqual(execution.checkpoint.call_count, 2)
        for index, (item, req, output) in enumerate(
            zip(result["item_results"], original_reqs, normalized_outputs),
            start=1,
        ):
            self.assertEqual(item["index"], index)
            self.assertEqual(item["id"], req["id"])
            self.assertEqual(item["type_key"], req["type_key"])
            self.assertEqual(item["prompt"], req["final_prompt"])
            self.assertEqual(item["req"], req)
            self.assertIsNot(item["req"], reqs[index - 1])
            self.assertEqual(item["file_path"], output["path"])
            self.assertEqual(item["output_metadata"], output)

        final_checkpoint = execution.checkpoint.call_args.kwargs
        self.assertEqual(final_checkpoint["result_files"], result["files"])

    def test_preserves_complete_frozen_request_for_reference_generation_and_normalization_failures(self):
        secret = "opaque-suite-secret"
        reqs = [
            self._request(
                "plan-01", "main-front", "Front", "load prompt", ["front-1"], ["missing.png"]
            ),
            self._request(
                "plan-02", "scene", "Scene", "generate prompt", ["front-1"], ["front.png"]
            ),
            self._request(
                "plan-03", "detail", "Detail", "normalize prompt", ["detail-1"], ["detail.png"]
            ),
        ]
        execution = self._execution(reqs)

        class PartiallyFailingClient:
            last_error = ""

            def compose_image_prompt(self, *_args):
                raise AssertionError("suite execution must not compose prompts")

            def generate_image(self, _references, prompt, *args):
                if prompt == "generate prompt":
                    raise RuntimeError("504 Gateway Time-out")
                return "generated-for-normalization"

            def get_last_error(self):
                return self.last_error

        def load_images(paths):
            if paths == ["missing.png"]:
                raise RuntimeError(f"reference loader echoed {secret}")
            return [f"loaded-{paths[0]}"]

        with (
            patch.object(
                app,
                "get_provider_by_id",
                return_value={"id": "provider-1", "api_key": secret},
            ),
            patch.object(app, "get_active_provider", return_value=None),
            patch.object(app, "load_image_paths", side_effect=load_images),
            patch.object(app, "create_ai_client", return_value=PartiallyFailingClient()),
            patch.object(
                app,
                "normalize_suite_image",
                side_effect=RuntimeError(f"normalizer echoed {secret}"),
            ),
        ):
            result = app._execute_combo_task(execution)

        self.assertTrue(result["partial"])
        self.assertEqual(result["files"], [])
        self.assertEqual(execution.checkpoint.call_count, 3)
        self.assertEqual(len(result["item_results"]), 3)
        for item, req in zip(result["item_results"], reqs):
            self.assertEqual(item["status"], "error")
            self.assertEqual(item["id"], req["id"])
            self.assertEqual(item["type_key"], req["type_key"])
            self.assertEqual(item["prompt"], req["final_prompt"])
            self.assertEqual(item["req"], req)
            self.assertNotIn(secret, item["error"])


if __name__ == "__main__":
    unittest.main()
