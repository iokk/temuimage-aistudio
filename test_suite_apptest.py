import tempfile
import unittest
import copy
from pathlib import Path
from unittest.mock import Mock, patch

from streamlit.testing.v1 import AppTest

import app
from task_store import SqliteTaskStore


def render_template_controls():
    import streamlit as st

    import app

    app._render_combo_template_controls({"scene": 1})
    st.write(st.session_state.get("combo_user_instruction", ""))


def render_stage_two():
    import streamlit as st

    import app

    if "combo_suite_draft" not in st.session_state:
        assets = [
            {
                "id": f"detail-{index}",
                "path": f"detail-{index}.jpg",
                "role": "detail",
            }
            for index in range(1, 6)
        ]
        draft = app.build_suite_editor_state(
            assets,
            product_identity="Black travel mug",
            selected_type_counts={"detail": 1},
        )
        st.session_state["combo_suite_draft"] = draft
        st.session_state["combo_suite_plan"] = app.finalize_suite_plan(draft)
        st.session_state["combo_images"] = []
        st.session_state["combo_submission_id"] = "original-submission"
    app._render_combo_stage_two({"id": "provider-1", "image_model": "model-1"})


def render_duplicate_submit():
    import streamlit as st
    from PIL import Image

    import app

    if "combo_suite_draft" not in st.session_state:
        assets = [{"id": "front-1", "path": "session.png", "role": "front"}]
        draft = app.build_suite_editor_state(
            assets,
            product_identity="Black travel mug",
            selected_type_counts={"main-front": 1},
        )
        st.session_state["combo_suite_draft"] = draft
        st.session_state["combo_suite_plan"] = app.finalize_suite_plan(draft)
        st.session_state["combo_images"] = [Image.new("RGB", (8, 8), "white")]
        st.session_state["combo_submission_id"] = "apptest-submission"
        st.session_state["combo_anchor"] = {"category": "mug"}
        st.session_state["combo_image_language"] = "English"
    if st.button("Submit", key="apptest_submit"):
        st.session_state["combo_generating"] = True
        task, error = app.consume_combo_generation_request(
            {"id": "provider-1", "vision_model": "gpt-4o-mini"},
            "model-1",
        )
        st.session_state["apptest_task_id"] = task.get("id") if task else ""
        st.session_state["apptest_error"] = error


class SuiteWorkspaceAppTests(unittest.TestCase):
    def test_template_application_restores_blueprint_and_global_instruction(self):
        template = {
            "id": "personal-launch",
            "name": "Launch",
            "type_counts": {"detail": 1},
            "plan_blueprint": [
                {
                    "type_key": "detail",
                    "theme": "Material launch",
                    "scene": "Bright studio",
                    "shot": "Macro close-up",
                    "composition": "Diagonal crop",
                    "copy_enabled": False,
                    "copy_text": "",
                }
            ],
            "global_settings": {"user_instruction": "Keep the handle visible."},
            "readonly": False,
            "system": False,
        }
        with patch.object(app, "load_personal_suite_templates", return_value=[template]):
            at = AppTest.from_function(render_template_controls).run()
            at.button(key="combo_apply_template").click().run()

        self.assertEqual(at.exception, [])
        self.assertEqual(at.session_state["combo_type_counts"]["detail"], 1)
        self.assertEqual(
            at.session_state["combo_user_instruction"],
            "Keep the handle visible.",
        )
        self.assertEqual(
            at.session_state["combo_applied_suite_template"]["plan_blueprint"][0]["theme"],
            "Material launch",
        )

    def test_stage_two_reference_picker_exposes_the_fourth_relevant_asset(self):
        at = AppTest.from_function(render_stage_two).run()

        self.assertEqual(at.exception, [])
        self.assertIn(
            "detail-4",
            at.multiselect(key="combo_plan_refs_plan-01").options,
        )

    def test_stage_two_copy_and_delete_buttons_mutate_the_plan_collection(self):
        at = AppTest.from_function(render_stage_two).run()

        at.button(key="combo_plan_copy_plan-01").click().run()
        self.assertEqual(at.exception, [])
        self.assertEqual(at.session_state["combo_suite_draft"]["target_count"], 2)
        self.assertEqual(
            [item["id"] for item in at.session_state["combo_suite_plan"]["plan_items"]],
            ["plan-01", "plan-02"],
        )

        at.button(key="combo_plan_delete_plan-02").click().run()
        self.assertEqual(at.exception, [])
        self.assertEqual(at.session_state["combo_suite_draft"]["target_count"], 1)
        self.assertEqual(
            [item["id"] for item in at.session_state["combo_suite_plan"]["plan_items"]],
            ["plan-01"],
        )

    def test_global_ai_replan_replaces_the_plan_and_submission_key(self):
        at = AppTest.from_function(render_stage_two).run()
        replanned = copy.deepcopy(at.session_state["combo_suite_plan"])
        replanned["plan_items"][0]["theme"] = "Fresh AI direction"
        client = Mock()
        client.generate_suite_plan.return_value = replanned
        client.get_tokens_used.return_value = 0

        with patch.object(app, "create_ai_client", return_value=client):
            at.button(key="combo_replan_suite").click().run()

        self.assertEqual(at.exception, [])
        self.assertEqual(
            at.session_state["combo_suite_plan"]["plan_items"][0]["theme"],
            "Fresh AI direction",
        )
        self.assertNotEqual(
            at.session_state["combo_submission_id"],
            "original-submission",
        )

    def test_duplicate_submission_clicks_create_one_task(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            data_dir = Path(temporary_directory)
            repository = SqliteTaskStore(data_dir / "tasks.sqlite3")
            with (
                patch.object(app, "DATA_DIR", data_dir),
                patch.object(app, "TASK_REPOSITORY", repository),
                patch.object(app, "get_session_owner_id", return_value="owner-a"),
                patch.object(app, "get_task_limits", return_value=(1, 20)),
            ):
                at = AppTest.from_function(render_duplicate_submit).run()
                at.button(key="apptest_submit").click().run()
                first_task_id = at.session_state["apptest_task_id"]
                at.button(key="apptest_submit").click().run()
                second_task_id = at.session_state["apptest_task_id"]

            tasks = repository.list(scope_owner_id="owner-a")

        self.assertEqual(at.exception, [])
        self.assertEqual(first_task_id, second_task_id)
        self.assertEqual(len(tasks), 1)


if __name__ == "__main__":
    unittest.main()
