import copy
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from PIL import Image

import app


class SuiteEditorStateTests(unittest.TestCase):
    def _assets(self):
        return [
            {"id": "front-1", "path": "front.jpg", "role": "front"},
            {"id": "detail-1", "path": "detail.jpg", "role": "detail"},
            {"id": "side-1", "path": "side.jpg", "role": "side"},
        ]

    def test_default_editor_state_builds_the_eight_image_suite(self):
        state = app.build_suite_editor_state(self._assets())

        self.assertEqual(app.MAX_TOTAL_IMAGES, 10)
        self.assertEqual(state["target_count"], 8)
        self.assertEqual(
            state["selected_type_counts"],
            {
                "main-front": 1,
                "back-side": 1,
                "detail": 3,
                "scene": 1,
                "dimension": 1,
                "selling-point": 1,
                "package": 0,
                "compare": 0,
                "steps": 0,
            },
        )

    def test_editor_state_rejects_more_than_ten_outputs(self):
        with self.assertRaisesRegex(ValueError, "1 and 10"):
            app.build_suite_editor_state(
                self._assets(),
                selected_type_counts={"scene": 11},
            )

    def test_editor_state_applies_user_role_corrections_before_planning(self):
        state = app.build_suite_editor_state(
            [{"path": "rear.jpg", "role": "rear", "role_confidence": 1.4}],
        )

        self.assertEqual(state["assets"][0]["id"], "asset-01")
        self.assertEqual(state["assets"][0]["role"], "back")
        self.assertEqual(state["assets"][0]["role_confidence"], 1.0)

    def test_dimension_data_is_kept_only_while_dimension_output_is_selected(self):
        enabled = app.build_suite_editor_state(
            self._assets(),
            selected_type_counts={"dimension": 1},
            dimension_data={"width": {"value": 18, "unit": "cm"}},
        )
        disabled = app.build_suite_editor_state(
            self._assets(),
            selected_type_counts={"scene": 1},
            dimension_data={"width": {"value": 18, "unit": "cm"}},
        )

        self.assertEqual(
            enabled["dimension_data"],
            {"width": {"value": 18, "unit": "cm"}},
        )
        self.assertEqual(disabled["dimension_data"], {})

    def test_editor_state_preserves_freeform_language_and_user_evidence(self):
        state = app.build_suite_editor_state(
            self._assets(),
            product_identity="Matte black travel mug with visible handle",
            product_summary="Visible brushed lid ring and ribbed handle",
            target_language="Canadian French, concise retail wording",
            user_instruction="Keep the handle visible in every full product view.",
            selling_points=["Leak-resistant lid", "Textured grip"],
        )

        self.assertEqual(
            state["target_language"],
            "Canadian French, concise retail wording",
        )
        self.assertEqual(
            state["product_identity"],
            "Matte black travel mug with visible handle",
        )
        self.assertEqual(
            state["product_summary"],
            "Visible brushed lid ring and ribbed handle",
        )
        self.assertEqual(
            state["selling_points"],
            ["Leak-resistant lid", "Textured grip"],
        )
        self.assertIn("handle visible", state["user_instruction"])

    def test_freeform_image_language_reaches_the_generation_instruction(self):
        instruction = app.get_image_language_instruction(
            "Canadian French, concise retail wording"
        )

        self.assertIn("Canadian French, concise retail wording", instruction)

    def test_plan_edits_revalidate_type_references_copy_and_frozen_prompt(self):
        draft = app.build_suite_editor_state(
            self._assets(),
            product_identity="Black handled mug",
            target_language="German",
            selected_type_counts={"scene": 1},
            selling_points=["Textured grip"],
        )
        initial = app.finalize_suite_plan(draft)
        edited_items = copy.deepcopy(initial["plan_items"])
        edited_items[0].update(
            {
                "type_key": "selling-point",
                "theme": "Grip comfort",
                "scene": "Bright kitchen counter",
                "shot": "Three-quarter close view",
                "composition": "Product left with text space",
                "copy_enabled": True,
                "copy_text": "Sicher im Griff",
                "reference_asset_ids": ["detail-1", "missing", "detail-1"],
            }
        )

        edited = app.apply_suite_plan_edits(draft, edited_items)
        item = edited["plan_items"][0]

        self.assertEqual(item["type_key"], "selling-point")
        self.assertEqual(item["reference_asset_ids"], ["detail-1", "front-1", "side-1"])
        self.assertTrue(item["copy_enabled"])
        self.assertEqual(item["copy_text"], "Sicher im Griff")
        self.assertIn("Bright kitchen counter", item["final_prompt"])
        self.assertIn("Sicher im Griff", item["final_prompt"])
        self.assertIn("German", item["final_prompt"])

    def test_supported_types_exclude_claim_comparison_and_steps_without_evidence(self):
        draft = app.build_suite_editor_state(
            [{"path": "front.jpg", "role": "front"}],
            selected_type_counts={"scene": 1},
        )

        self.assertEqual(
            app.get_supported_suite_types(draft),
            ["main-front", "scene"],
        )

        evidenced = app.build_suite_editor_state(
            [
                {"path": "front.jpg", "role": "front"},
                {"path": "detail.jpg", "role": "detail"},
                {"path": "package.jpg", "role": "package"},
            ],
            selected_type_counts={"scene": 1},
            selling_points=["Textured grip"],
        )
        self.assertEqual(
            app.get_supported_suite_types(evidenced),
            ["main-front", "detail", "scene", "selling-point", "package"],
        )

    def test_upload_change_invalidates_analysis_and_plans_but_same_upload_does_not(self):
        old_plan = {"plan_items": [{"id": "plan-01"}]}
        state = {
            "combo_upload_signature": "old-signature",
            "combo_suite_analysis": {"assets": [{"id": "asset-01"}]},
            "combo_suite_draft": {"target_count": 1},
            "combo_suite_plan": old_plan,
            "combo_suite_stage": 2,
            "combo_asset_role_0": "front",
            "combo_product_identity": "Old product",
            "combo_selling_points": "Old claim",
            "combo_dimension_width": "99",
        }

        changed = app.sync_combo_upload_state(
            state,
            [Image.new("RGB", (8, 8), "white")],
            "new-signature",
        )
        self.assertTrue(changed)
        self.assertEqual(state["combo_suite_stage"], 1)
        self.assertIsNone(state["combo_suite_analysis"])
        self.assertIsNone(state["combo_suite_draft"])
        self.assertIsNone(state["combo_suite_plan"])
        self.assertNotIn("combo_asset_role_0", state)
        self.assertNotIn("combo_dimension_width", state)
        self.assertEqual(state["combo_product_identity"], "")
        self.assertEqual(state["combo_selling_points"], "")

        state["combo_suite_plan"] = old_plan
        unchanged = app.sync_combo_upload_state(
            state,
            [Image.new("RGB", (8, 8), "black")],
            "new-signature",
        )
        self.assertFalse(unchanged)
        self.assertIs(state["combo_suite_plan"], old_plan)

    def test_personal_templates_validate_deduplicate_and_restore_system_default(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            settings_file = Path(temporary_directory) / "settings.json"
            with patch.object(app, "SETTINGS_FILE", settings_file):
                app._CONFIG_CACHE.clear()
                app.save_personal_suite_template(
                    "Launch set",
                    {"main-front": 1, "detail": 2, "scene": 1},
                )
                app.save_personal_suite_template(
                    "launch SET",
                    {"main-front": 1, "scene": 2},
                )

                templates = app.load_personal_suite_templates()
                self.assertEqual(len(templates), 2)
                self.assertTrue(templates[0]["readonly"])
                self.assertEqual(templates[0]["type_counts"]["detail"], 3)
                self.assertEqual(templates[1]["name"], "launch SET")
                self.assertEqual(sum(templates[1]["type_counts"].values()), 3)

                templates[0]["type_counts"]["detail"] = 0
                self.assertEqual(
                    app.load_personal_suite_templates()[0]["type_counts"]["detail"],
                    3,
                )

                app.delete_personal_suite_template("LAUNCH set")
                restored = app.load_personal_suite_templates()
                self.assertEqual(len(restored), 1)
                self.assertEqual(restored[0]["id"], "temu-standard")

                with self.assertRaises(ValueError):
                    app.save_personal_suite_template("TEMU 标准套图", {"scene": 1})
                with self.assertRaises(ValueError):
                    app.save_personal_suite_template("Too many", {"scene": 11})
                with self.assertRaises(ValueError):
                    app.save_personal_suite_template("Unknown", {"invented": 1})

    def test_personal_template_blueprints_are_owner_scoped_and_sanitized(self):
        plan_items = [
            {
                "id": "plan-01",
                "type_key": "main-front",
                "theme": "Clean catalog launch",
                "scene": "Pure white studio",
                "shot": "Straight-on front view",
                "composition": "Centered complete product",
                "copy_enabled": True,
                "copy_text": "Built for daily use",
                "reference_asset_ids": ["old-front"],
                "final_prompt": "old product prompt",
                "product_identity": "old product",
            }
        ]
        expected_fields = {
            "type_key",
            "theme",
            "scene",
            "shot",
            "composition",
            "copy_enabled",
            "copy_text",
        }

        with tempfile.TemporaryDirectory() as temporary_directory:
            settings_file = Path(temporary_directory) / "settings.json"
            with patch.object(app, "SETTINGS_FILE", settings_file):
                app._CONFIG_CACHE.clear()
                app.save_personal_suite_template(
                    "Launch set",
                    {"main-front": 1},
                    plan_items=plan_items,
                    user_instruction="Use bright natural light.",
                    owner_id="owner-a",
                )

                owner_a = app.load_personal_suite_templates(owner_id="owner-a")
                owner_b = app.load_personal_suite_templates(owner_id="owner-b")
                stored_settings = json.loads(settings_file.read_text(encoding="utf-8"))

        self.assertEqual(len(owner_a), 2)
        self.assertEqual(len(owner_b), 1)
        self.assertEqual(set(owner_a[1]["plan_blueprint"][0]), expected_fields)
        self.assertEqual(
            owner_a[1]["global_settings"],
            {"user_instruction": "Use bright natural light."},
        )
        self.assertEqual(
            list(stored_settings["suite_templates"]["owners"]),
            ["owner-a"],
        )

    def test_template_blueprint_reuses_direction_but_reselects_new_product_references(self):
        old_plan_item = {
            "type_key": "main-front",
            "theme": "Clean catalog launch",
            "scene": "Pure white studio",
            "shot": "Straight-on front view",
            "composition": "Centered complete product",
            "copy_enabled": True,
            "copy_text": "Ready for every day",
            "reference_asset_ids": ["old-front"],
            "final_prompt": "old frozen prompt",
        }
        with tempfile.TemporaryDirectory() as temporary_directory:
            settings_file = Path(temporary_directory) / "settings.json"
            with patch.object(app, "SETTINGS_FILE", settings_file):
                app._CONFIG_CACHE.clear()
                app.save_personal_suite_template(
                    "Reusable launch",
                    {"main-front": 1},
                    plan_items=[old_plan_item],
                    user_instruction="Keep the complete product visible.",
                    owner_id="owner-a",
                )
                template = app.load_personal_suite_templates(owner_id="owner-a")[1]

        new_draft = app.build_suite_editor_state(
            [{"id": "new-front", "path": "new-front.jpg", "role": "front"}],
            product_identity="New red kettle",
            product_summary="Visible arched handle and steel spout",
            selected_type_counts={"main-front": 1},
        )
        new_plan = app.finalize_suite_plan(new_draft)

        merged_draft, merged_plan = app.apply_suite_template_blueprint(
            new_draft, new_plan, template
        )
        item = merged_plan["plan_items"][0]

        self.assertEqual(item["theme"], "Clean catalog launch")
        self.assertEqual(item["reference_asset_ids"], ["new-front"])
        self.assertNotEqual(item["final_prompt"], "old frozen prompt")
        self.assertIn("New red kettle", item["final_prompt"])
        self.assertIn("Visible arched handle and steel spout", item["final_prompt"])
        self.assertIn("Keep the complete product visible", item["final_prompt"])
        self.assertEqual(
            merged_draft["user_instruction"],
            "Keep the complete product visible.",
        )

    def test_concurrent_template_saves_do_not_lose_owner_records(self):
        failures = []
        barrier = threading.Barrier(9)

        with tempfile.TemporaryDirectory() as temporary_directory:
            settings_file = Path(temporary_directory) / "settings.json"
            with patch.object(app, "SETTINGS_FILE", settings_file):
                app._CONFIG_CACHE.clear()

                def save_template(index):
                    try:
                        barrier.wait()
                        app.save_personal_suite_template(
                            f"Template {index}",
                            {"scene": 1},
                            owner_id="shared-owner",
                        )
                    except BaseException as error:
                        failures.append(error)

                threads = [
                    threading.Thread(target=save_template, args=(index,))
                    for index in range(8)
                ]
                for thread in threads:
                    thread.start()
                barrier.wait()
                for thread in threads:
                    thread.join(timeout=10)

                templates = app.load_personal_suite_templates(owner_id="shared-owner")

        self.assertTrue(all(not thread.is_alive() for thread in threads))
        self.assertEqual(failures, [])
        self.assertEqual(
            {template["name"] for template in templates[1:]},
            {f"Template {index}" for index in range(8)},
        )

    def test_plan_collection_copy_and_delete_reindex_and_sync_the_draft(self):
        draft = app.build_suite_editor_state(
            [{"id": "front-1", "path": "front.jpg", "role": "front"}],
            selected_type_counts={"scene": 2},
        )
        plan = app.finalize_suite_plan(draft)

        copied_draft, copied_plan = app.mutate_suite_plan_collection(
            draft, plan, action="copy", item_id="plan-01"
        )
        deleted_draft, deleted_plan = app.mutate_suite_plan_collection(
            copied_draft, copied_plan, action="delete", item_id="plan-02"
        )

        self.assertEqual(copied_draft["target_count"], 3)
        self.assertEqual(copied_draft["selected_type_counts"]["scene"], 3)
        self.assertEqual(
            [item["id"] for item in copied_plan["plan_items"]],
            ["plan-01", "plan-02", "plan-03"],
        )
        self.assertEqual(copied_plan["plan_items"][1]["scene"], plan["plan_items"][0]["scene"])
        self.assertTrue(all(item["final_prompt"] for item in copied_plan["plan_items"]))
        self.assertEqual(deleted_draft["target_count"], 2)
        self.assertEqual(deleted_draft["selected_type_counts"]["scene"], 2)
        self.assertEqual(
            [item["id"] for item in deleted_plan["plan_items"]],
            ["plan-01", "plan-02"],
        )

    def test_plan_collection_enforces_one_to_ten_items(self):
        one_draft = app.build_suite_editor_state(
            [{"id": "front-1", "path": "front.jpg", "role": "front"}],
            selected_type_counts={"scene": 1},
        )
        one_plan = app.finalize_suite_plan(one_draft)
        ten_draft = app.build_suite_editor_state(
            [{"id": "front-1", "path": "front.jpg", "role": "front"}],
            selected_type_counts={"scene": 10},
        )
        ten_plan = app.finalize_suite_plan(ten_draft)

        with self.assertRaisesRegex(ValueError, "at least one"):
            app.mutate_suite_plan_collection(
                one_draft, one_plan, action="delete", item_id="plan-01"
            )
        with self.assertRaisesRegex(ValueError, "at most ten"):
            app.mutate_suite_plan_collection(
                ten_draft, ten_plan, action="copy", item_id="plan-01"
            )


class SuiteAINormalizationTests(unittest.TestCase):
    def _client(self):
        client = object.__new__(app.GeminiClient)
        client.api_key = "test-key"
        client.total_tokens = 0
        client.last_error = None
        return client

    def test_asset_analysis_stays_aligned_to_upload_order_and_normalizes_fields(self):
        client = self._client()
        response = """{
          "product_identity": "black travel mug",
          "assets": [
            {"upload_index": 2, "role": "close-up", "confidence": 1.8, "flags": ["watermark", 7]},
            {"upload_index": 1, "role": "rear", "confidence": 0.82, "quality_flags": ["low-resolution"]}
          ]
        }"""
        images = [Image.new("RGB", (8, 8), "white") for _ in range(3)]

        with patch.object(client, "_vision_request", return_value=response):
            result = client.analyze_suite_assets(images)

        self.assertEqual(result["product_identity"], "black travel mug")
        self.assertEqual(
            [(asset["id"], asset["upload_index"], asset["role"]) for asset in result["assets"]],
            [
                ("asset-01", 1, "back"),
                ("asset-02", 2, "detail"),
                ("asset-03", 3, "unknown"),
            ],
        )
        self.assertEqual(result["assets"][0]["role_confidence"], 0.82)
        self.assertEqual(result["assets"][1]["role_confidence"], 1.0)
        self.assertEqual(result["assets"][1]["quality_flags"], ["watermark"])

    def test_malformed_asset_analysis_uses_one_deterministic_fallback_per_upload(self):
        client = self._client()
        images = [Image.new("RGB", (8, 8), "white") for _ in range(2)]

        with patch.object(client, "_vision_request", return_value="not json"):
            result = client.analyze_suite_assets(images)

        self.assertEqual([asset["id"] for asset in result["assets"]], ["asset-01", "asset-02"])
        self.assertEqual([asset["role"] for asset in result["assets"]], ["unknown", "unknown"])
        self.assertTrue(all("analysis-unavailable" in asset["quality_flags"] for asset in result["assets"]))

    def test_suite_planning_accepts_ai_copy_and_invalid_json_falls_back_without_raising(self):
        client = self._client()
        draft = app.build_suite_editor_state(
            [{"id": "front-1", "path": "front.jpg", "role": "front"}],
            product_identity="Black mug",
            target_language="Spanish",
            selected_type_counts={"main-front": 1},
        )
        ai_response = """{
          "plan_items": [{
            "type_key": "main-front",
            "theme": "Clean catalog hero",
            "scene": "Pure white studio",
            "shot": "Straight-on front view",
            "composition": "Centered complete product",
            "copy_enabled": true,
            "copy_text": "Diseño limpio",
            "reference_asset_ids": ["front-1"]
          }]
        }"""

        with patch.object(client, "_text_request", return_value=ai_response):
            planned = client.generate_suite_plan(draft)
        with patch.object(client, "_text_request", return_value="{broken"):
            fallback = client.generate_suite_plan(draft)

        self.assertTrue(planned["used_ai_plan"])
        self.assertEqual(planned["plan_items"][0]["copy_text"], "Diseño limpio")
        self.assertIn("Diseño limpio", planned["plan_items"][0]["final_prompt"])
        self.assertFalse(fallback["used_ai_plan"])
        self.assertEqual(len(fallback["plan_items"]), 1)
        self.assertTrue(fallback["plan_items"][0]["final_prompt"])

    def test_valid_suite_plan_uses_one_ai_request(self):
        client = self._client()
        draft = app.build_suite_editor_state(
            [{"id": "front-1", "path": "front.jpg", "role": "front"}],
            selected_type_counts={"main-front": 1},
        )
        valid_response = """{"plan_items":[{"type_key":"main-front","theme":"Catalog clarity","scene":"White studio","shot":"Front view","composition":"Centered product","copy_enabled":false,"copy_text":"","reference_asset_ids":["front-1"]}]}"""

        with patch.object(client, "_text_request", return_value=valid_response) as request:
            result = client.generate_suite_plan(draft)

        self.assertTrue(result["used_ai_plan"])
        self.assertEqual(request.call_count, 1)

    def test_invalid_suite_plan_is_retried_once_with_correction_instruction(self):
        client = self._client()
        draft = app.build_suite_editor_state(
            [{"id": "front-1", "path": "front.jpg", "role": "front"}],
            selected_type_counts={"main-front": 1},
        )
        valid_response = """{"plan_items":[{"type_key":"main-front","theme":"Catalog clarity","scene":"White studio","shot":"Front view","composition":"Centered product","copy_enabled":false,"copy_text":"","reference_asset_ids":["front-1"]}]}"""

        with patch.object(
            client, "_text_request", side_effect=["{broken", valid_response]
        ) as request:
            result = client.generate_suite_plan(draft)

        self.assertTrue(result["used_ai_plan"])
        self.assertEqual(request.call_count, 2)
        self.assertIn("correct", request.call_args_list[1].args[0].lower())

    def test_two_invalid_suite_plan_responses_fall_back_after_two_requests(self):
        client = self._client()
        draft = app.build_suite_editor_state(
            [{"id": "front-1", "path": "front.jpg", "role": "front"}],
            selected_type_counts={"main-front": 1},
        )

        with patch.object(
            client, "_text_request", side_effect=["{broken", "[]"]
        ) as request:
            result = client.generate_suite_plan(draft)

        self.assertFalse(result["used_ai_plan"])
        self.assertEqual(request.call_count, 2)

    def test_demo_suite_methods_are_deterministic_and_make_no_upstream_request(self):
        client = self._client()
        client.api_key = app.DEMO_PROVIDER_KEY
        images = [Image.new("RGB", (8, 8), "white")]
        draft = app.build_suite_editor_state(
            [{"id": "front-1", "path": "front.jpg", "role": "front"}],
            selected_type_counts={"main-front": 1},
        )

        with (
            patch.object(client, "_vision_request", side_effect=AssertionError("network")),
            patch.object(client, "_text_request", side_effect=AssertionError("network")),
        ):
            analysis = client.analyze_suite_assets(images)
            plan = client.generate_suite_plan(draft)

        self.assertEqual(analysis["assets"][0]["id"], "asset-01")
        self.assertEqual(analysis["assets"][0]["role"], "front")
        self.assertFalse(plan["used_ai_plan"])


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

    def test_retry_snapshot_rejects_a_canonical_asset_path_swapped_for_another_durable_path(self):
        retry_payload = self._suite_payload()
        retry_payload["retry_parent_id"] = "parent-task"
        retry_payload["reqs"] = retry_payload["reqs"][:1]
        retry_payload["reqs"][0]["image_paths"] = ["/durable/detail.png"]

        errors = app._validate_combo_task_payload(retry_payload)

        self.assertTrue(any("冻结计划不一致" in error for error in errors))

        retry_payload["reqs"][0]["image_paths"] = ["/durable/front.png"]
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

    def test_snapshot_validation_requires_one_unique_top_level_path_per_plan_asset(self):
        missing_path = self._suite_payload()
        missing_path["image_paths"] = missing_path["image_paths"][:-1]
        duplicate_path = self._suite_payload()
        duplicate_path["image_paths"][1] = duplicate_path["image_paths"][0]

        self.assertTrue(
            any(
                "数量必须一致" in error
                for error in app._validate_combo_task_payload(missing_path)
            )
        )
        self.assertTrue(
            any(
                "必须保持唯一" in error
                for error in app._validate_combo_task_payload(duplicate_path)
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

    def test_duplicate_suite_submission_reuses_one_task_without_rewriting_uploads(self):
        from task_store import SqliteTaskStore

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
            "combo_submission_id": "stable-suite-submission",
            "combo_images": [Image.new("RGB", (8, 8), "white")],
            "combo_anchor": {"category": "mug"},
            "combo_suite_draft": suite_draft,
            "combo_suite_plan": suite_plan,
            "combo_image_language": "English",
            "combo_enable_title": False,
            "combo_title_info": "",
        }
        provider = {
            "id": "provider-1",
            "title_model": "gpt-4o-mini",
            "vision_model": "gpt-4o-mini",
        }

        with tempfile.TemporaryDirectory() as temporary_directory:
            data_dir = Path(temporary_directory)
            repository = SqliteTaskStore(data_dir / "tasks.sqlite3")
            original_save = app._save_uploaded_images
            with (
                patch.object(app, "DATA_DIR", data_dir),
                patch.object(app, "TASK_REPOSITORY", repository),
                patch.object(app, "get_session_owner_id", return_value="owner-a"),
                patch.object(app, "get_task_limits", return_value=(1, 20)),
                patch.object(
                    app,
                    "_save_uploaded_images",
                    wraps=original_save,
                ) as save_uploads,
            ):
                first = app.consume_combo_generation_request(
                    provider, "fallback-model", state=state
                )
                state["combo_generating"] = True
                replayed = app.consume_combo_generation_request(
                    provider, "fallback-model", state=state
                )

            persisted_tasks = repository.list(scope_owner_id="owner-a")

        self.assertEqual(first[1], "")
        self.assertEqual(replayed[1], "")
        self.assertEqual(first[0]["id"], replayed[0]["id"])
        self.assertEqual(save_uploads.call_count, 1)
        self.assertEqual(len(persisted_tasks), 1)
        self.assertEqual(
            persisted_tasks[0]["submission_id"],
            "stable-suite-submission",
        )

    def test_failed_suite_submission_removes_only_files_created_for_that_attempt(self):
        state = {
            "combo_generating": True,
            "combo_submission_id": "invalid-suite-submission",
            "combo_images": [Image.new("RGB", (8, 8), "white")],
            "combo_suite_draft": {"target_count": 1},
            "combo_suite_plan": {
                "assets": [{"id": "front-1"}, {"id": "extra-1"}],
                "plan_items": [],
            },
        }
        provider = {"id": "provider-1"}

        with tempfile.TemporaryDirectory() as temporary_directory:
            data_dir = Path(temporary_directory)
            upload_dir = data_dir / "task_uploads"
            upload_dir.mkdir(parents=True)
            unrelated = upload_dir / "unrelated.png"
            unrelated.write_bytes(b"keep")
            with (
                patch.object(app, "DATA_DIR", data_dir),
                patch.object(app, "get_session_owner_id", return_value="owner-a"),
            ):
                task, error = app.consume_combo_generation_request(
                    provider, "fallback-model", state=state
                )

            remaining = sorted(path.name for path in upload_dir.iterdir())

        self.assertIsNone(task)
        self.assertIn("持久化不完整", error)
        self.assertEqual(remaining, ["unrelated.png"])


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

    def test_legacy_persistence_failure_still_fails_the_combo_task(self):
        execution = Mock()
        execution.task = {
            "id": "legacy-persistence",
            "type": "combo",
            "payload": {
                "provider_id": "provider-1",
                "image_paths": ["reference.png"],
                "reqs": [{"type_name": "Front hero"}],
            },
        }

        class LegacyClient:
            last_error = ""

            def compose_image_prompt(self, *_args):
                return "legacy composed prompt"

            def generate_image(self, *_args):
                return Image.new("RGB", (16, 16), "white")

            def get_last_error(self):
                return self.last_error

        with (
            patch.object(
                app,
                "get_provider_by_id",
                return_value={"id": "provider-1", "api_key": "test-key"},
            ),
            patch.object(app, "get_active_provider", return_value=None),
            patch.object(app, "load_image_paths", return_value=[object()]),
            patch.object(app, "create_ai_client", return_value=LegacyClient()),
            patch.object(
                app,
                "persist_image_for_task",
                side_effect=RuntimeError("legacy disk write failed"),
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "legacy disk write failed"):
                app._execute_combo_task(execution)

        execution.checkpoint.assert_not_called()

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
            def __init__(self):
                self._last_error = "unchanged-provider-error"
                self.last_error_updates = []

            @property
            def last_error(self):
                return self._last_error

            @last_error.setter
            def last_error(self, value):
                self.last_error_updates.append(value)
                self._last_error = value

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
                raise RuntimeError(f"local reference timeout 504 echoed {secret}")
            return [f"loaded-{paths[0]}"]

        client = PartiallyFailingClient()
        with (
            patch.object(
                app,
                "get_provider_by_id",
                return_value={"id": "provider-1", "api_key": secret},
            ),
            patch.object(app, "get_active_provider", return_value=None),
            patch.object(app, "load_image_paths", side_effect=load_images),
            patch.object(app, "create_ai_client", return_value=client),
            patch.object(
                app,
                "normalize_suite_image",
                side_effect=RuntimeError(
                    f"local output normalization timeout 504 echoed {secret}"
                ),
            ),
        ):
            result = app._execute_combo_task(execution)

        self.assertTrue(result["partial"])
        self.assertEqual(result["files"], [])
        self.assertEqual(execution.checkpoint.call_count, 3)
        self.assertEqual(len(result["item_results"]), 3)
        self.assertEqual(
            [item["error_type"] for item in result["item_results"]],
            ["reference_load_error", "upstream_timeout", "output_normalization_error"],
        )
        self.assertEqual(
            [item["retryable"] for item in result["item_results"]],
            [False, True, False],
        )
        self.assertEqual(
            client.last_error_updates,
            ["请求超时，请检查网络、代理或模型响应速度。"],
        )
        for item, req in zip(result["item_results"], reqs):
            self.assertEqual(item["status"], "error")
            self.assertEqual(item["id"], req["id"])
            self.assertEqual(item["type_key"], req["type_key"])
            self.assertEqual(item["prompt"], req["final_prompt"])
            self.assertEqual(item["req"], req)
            self.assertNotIn(secret, item["error"])


if __name__ == "__main__":
    unittest.main()
