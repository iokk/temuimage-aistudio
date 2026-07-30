import json
import multiprocessing
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import app
from task_engine import TaskExecution
from task_store import SqliteTaskStore


TERMINAL_STATUSES = {"done", "partial", "error", "cancelled", "expired"}


def make_task(task_id: str, created_at: str = "2026-07-29T10:00:00") -> dict:
    return {
        "id": task_id,
        "type": "text_to_image",
        "status": "queued",
        "owner_id": "test-workspace",
        "created_at": created_at,
        "updated_at": created_at,
        "payload": {"prompt": f"prompt for {task_id}"},
        "errors": [],
        "result_files": [],
        "result_title_language": "zh",
    }


def mutate_shared_history(lock_path: str, history_path: str, task_id: str) -> None:
    lock = app._InterProcessHistoryLock(Path(lock_path))
    with lock:
        path = Path(history_path)
        records = json.loads(path.read_text(encoding="utf-8"))
        time.sleep(0.05)
        records.append(task_id)
        path.write_text(json.dumps(records), encoding="utf-8")


class SimulatedProcessInterruption(BaseException):
    """Models abrupt interpreter loss after a checkpoint transaction commits."""


class ComboSubmissionTests(unittest.TestCase):
    def test_pending_combo_request_creates_one_task_and_is_consumed(self):
        submit = getattr(app, "consume_combo_generation_request", None)
        self.assertTrue(callable(submit))
        state = {
            "combo_generating": True,
            "combo_images": [],
            "combo_reqs": [{"type_name": "主图", "prompt": "clean product"}],
            "combo_anchor": {"category": "mug"},
            "combo_image_language": "zh",
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
                return_value=({"id": "combo-task"}, ""),
            ) as create_task,
        ):
            first = submit(provider, "fallback-model", state=state)
            second = submit(provider, "fallback-model", state=state)

        self.assertEqual(first, ({"id": "combo-task"}, ""))
        self.assertEqual(second, (None, ""))
        self.assertFalse(state["combo_generating"])
        self.assertEqual(create_task.call_count, 1)
        task_type, payload = create_task.call_args.args
        self.assertEqual(task_type, "combo")
        self.assertEqual(payload["provider_id"], "provider-1")
        self.assertEqual(payload["total"], 1)
        self.assertEqual(payload["model"], "fallback-model")


class TranslationErrorSecurityTests(unittest.TestCase):
    def test_provider_secret_is_sanitized_before_translation_log_and_checkpoint(self):
        opaque_secret = "opaque-translation-secret-123"

        class FailingClient:
            def __init__(self):
                self.last_error = ""

            def generate_image(self, *_args, **_kwargs):
                raise RuntimeError(f"upstream echoed {opaque_secret}")

            def get_last_error(self):
                return self.last_error

        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = SqliteTaskStore(
                Path(temporary_directory) / "translation-security.sqlite3"
            )
            task = make_task("translation-security")
            task.update(
                {
                    "type": "translate",
                    "payload": {
                        "provider_id": "provider-1",
                        "image_paths": ["one.png"],
                        "image_language": "zh",
                    },
                }
            )
            repository.create(task, 10, TERMINAL_STATUSES)
            claimed = repository.claim_next(1, "translation-runner")
            execution = TaskExecution(repository, claimed)
            provider = {
                "id": "provider-1",
                "api_key": opaque_secret,
                "secret_storage": "runtime",
                "image_model": "test-image",
            }
            client = FailingClient()

            with (
                patch.object(app, "get_provider_by_id", return_value=provider),
                patch.object(app, "get_active_provider", return_value=None),
                patch.object(app, "load_image_paths", return_value=[object()]),
                patch.object(app, "create_ai_client", return_value=client),
                self.assertLogs("xiaobaitu", level="ERROR") as captured,
                self.assertRaises(Exception) as failure,
            ):
                app._execute_translate_task(execution)

            persisted = repository.get(task["id"])

        evidence = "\n".join(captured.output)
        evidence += "\n" + str(failure.exception)
        evidence += "\n" + json.dumps(persisted, ensure_ascii=False)
        self.assertNotIn(opaque_secret, evidence)
        self.assertIn("[REDACTED]", evidence)


class CheckpointInterruptingRepository:
    def __init__(
        self,
        repository,
        interrupt_after_done,
        first_checkpoint_event=None,
        interruption_event=None,
    ):
        self.repository = repository
        self.interrupt_after_done = interrupt_after_done
        self.first_checkpoint_event = first_checkpoint_event
        self.interruption_event = interruption_event
        self.interrupted = False

    def __getattr__(self, name):
        return getattr(self.repository, name)

    def update(self, task_id, updates, **expectations):
        persisted = self.repository.update(task_id, updates, **expectations)
        progress = updates.get("progress") or {}
        completed = progress.get("done", 0)
        if persisted and completed == 1 and self.first_checkpoint_event:
            self.first_checkpoint_event.set()
        if (
            persisted
            and completed >= self.interrupt_after_done
            and not self.interrupted
        ):
            self.interrupted = True
            if self.interruption_event:
                self.interruption_event.set()
            raise SimulatedProcessInterruption("process stopped after checkpoint")
        return persisted


class FakeImage:
    def __init__(self, label):
        self.label = label


class SequentialBatchClient:
    def __init__(self, successful_label):
        self.successful_label = successful_label
        self.calls = 0
        self.last_error = ""

    def compose_image_prompt(self, anchor, requirement, aspect, image_language):
        return requirement.get("prompt", "")

    def generate_image(self, references, prompt, *args):
        self.calls += 1
        if self.calls == 1:
            return FakeImage(self.successful_label)
        if self.calls == 2:
            raise RuntimeError("second item failed upstream")
        raise AssertionError("third item must not start before the checkpoint")

    def get_last_error(self):
        return self.last_error


class ConcurrentSmartClient:
    def __init__(self, first_checkpoint_event, interruption_event):
        self.first_checkpoint_event = first_checkpoint_event
        self.interruption_event = interruption_event

    def generate_image(self, references, prompt, *args):
        if prompt == "first-success":
            return FakeImage("smart-first")
        if prompt == "second-error":
            if not self.first_checkpoint_event.wait(timeout=2):
                raise AssertionError("first checkpoint was not persisted")
            raise RuntimeError("second item failed upstream")
        if prompt == "third-pending":
            if not self.interruption_event.wait(timeout=2):
                raise AssertionError("interruption checkpoint was not reached")
            return FakeImage("smart-third")
        raise AssertionError(f"unexpected prompt: {prompt}")

    def get_last_error(self):
        return ""


class TaskCheckpointRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.database_path = (
            Path(self.temporary_directory.name) / "checkpoint-tasks.sqlite3"
        )
        self.repository = SqliteTaskStore(self.database_path)
        self.runner_id = "checkpoint-runner"
        self.provider = {
            "id": "provider-1",
            "api_key": "test-key",
            "image_model": "test-image",
        }

    def run_until_second_checkpoint(
        self, task, client, first_event=None, stop_event=None
    ):
        self.repository.create(task, 10, TERMINAL_STATUSES)
        claimed = self.repository.claim_next(1, self.runner_id)
        interrupting_repository = CheckpointInterruptingRepository(
            self.repository,
            interrupt_after_done=2,
            first_checkpoint_event=first_event,
            interruption_event=stop_event,
        )

        def persist_image(image, filename):
            return f"/virtual/{image.label}.png"

        execution = TaskExecution(interrupting_repository, claimed)
        executor = {
            "smart": app._execute_smart_task,
            "translate": app._execute_translate_task,
            "combo": app._execute_combo_task,
        }[task["type"]]
        with (
            patch.object(app, "get_provider_by_id", return_value=self.provider),
            patch.object(app, "get_active_provider", return_value=None),
            patch.object(
                app,
                "load_image_paths",
                return_value=[object(), object(), object()],
            ),
            patch.object(app, "create_ai_client", return_value=client),
            patch.object(app, "persist_image_for_task", side_effect=persist_image),
        ):
            with self.assertRaises(SimulatedProcessInterruption):
                executor(execution)

        return SqliteTaskStore(self.database_path).get(task["id"])

    def assert_recoverable_checkpoint(self, recovered, expected_file):
        self.assertEqual(recovered["status"], "running")
        self.assertEqual(recovered["result_files"], [expected_file])
        self.assertEqual(recovered["progress"]["done"], 2)
        self.assertEqual(recovered["progress"]["total"], 3)
        self.assertEqual(len(recovered["errors"]), 1)
        item_results = recovered.get("item_results", [])
        self.assertEqual(
            [item.get("status") for item in item_results],
            ["done", "error"],
            "each finished batch item must be recoverable from the task repository",
        )
        self.assertEqual(item_results[0]["file_path"], expected_file)
        self.assertTrue(item_results[1].get("error"))

    def test_smart_task_recovers_completed_files_and_item_outcomes_after_interruption(self):
        first_checkpoint = threading.Event()
        interruption = threading.Event()
        task = make_task("smart-checkpoint")
        task.update(
            {
                "type": "smart",
                "payload": {
                    "provider_id": self.provider["id"],
                    "image_paths": ["input.png"],
                    "retry_items": [
                        {
                            "type_name": "First",
                            "index": 1,
                            "prompt": "first-success",
                        },
                        {
                            "type_name": "Second",
                            "index": 2,
                            "prompt": "second-error",
                        },
                        {
                            "type_name": "Third",
                            "index": 3,
                            "prompt": "third-pending",
                        },
                    ],
                    "image_language": "zh",
                },
            }
        )
        client = ConcurrentSmartClient(first_checkpoint, interruption)

        recovered = self.run_until_second_checkpoint(
            task,
            client,
            first_event=first_checkpoint,
            stop_event=interruption,
        )

        self.assert_recoverable_checkpoint(recovered, "/virtual/smart-first.png")

    def test_translate_task_recovers_completed_files_and_item_outcomes_after_interruption(self):
        task = make_task("translate-checkpoint")
        task.update(
            {
                "type": "translate",
                "payload": {
                    "provider_id": self.provider["id"],
                    "image_paths": ["one.png", "two.png", "three.png"],
                    "image_language": "zh",
                },
            }
        )
        client = SequentialBatchClient("translate-first")

        recovered = self.run_until_second_checkpoint(task, client)

        self.assertEqual(client.calls, 2)
        self.assert_recoverable_checkpoint(recovered, "/virtual/translate-first.png")

    def test_combo_task_recovers_completed_files_and_item_outcomes_after_interruption(self):
        task = make_task("combo-checkpoint")
        task.update(
            {
                "type": "combo",
                "payload": {
                    "provider_id": self.provider["id"],
                    "image_paths": ["reference.png"],
                    "reqs": [
                        {"type_name": "First", "index": 1, "prompt": "first"},
                        {"type_name": "Second", "index": 2, "prompt": "second"},
                        {"type_name": "Third", "index": 3, "prompt": "third"},
                    ],
                    "image_language": "zh",
                },
            }
        )
        client = SequentialBatchClient("combo-first")

        recovered = self.run_until_second_checkpoint(task, client)

        self.assertEqual(client.calls, 2)
        self.assert_recoverable_checkpoint(recovered, "/virtual/combo-first.png")


class TaskHistoryArchivingTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.directory = Path(self.temporary_directory.name)
        self.repository = SqliteTaskStore(self.directory / "tasks.sqlite3")
        task = make_task("history-task")
        task["status"] = "done"
        self.repository.create(task, 10, TERMINAL_STATUSES)
        self.task = task

    def archive_patches(self, save_succeeds):
        return (
            patch.object(app, "TASK_REPOSITORY", self.repository),
            patch.object(app, "get_history_data", return_value={"records": []}),
            patch.object(
                app,
                "_history_record_dir",
                return_value=self.directory / "project-history",
            ),
            patch.object(
                app, "_copy_input_files_for_history", return_value=({}, [])
            ),
            patch.object(app, "_write_project_text_files"),
            patch.object(app, "_write_history_zip", return_value=""),
            patch.object(app, "save_history_data", return_value=save_succeeds),
        )

    def test_history_repair_only_replays_unarchived_terminal_tasks(self):
        repository = SqliteTaskStore(self.directory / "repair-tasks.sqlite3")
        completed = make_task("completed")
        completed["status"] = "done"
        archived = make_task("archived", "2026-07-29T10:01:00")
        archived.update(
            {"status": "error", "history_archived_at": "2026-07-29T10:02:00"}
        )
        queued = make_task("still-queued", "2026-07-29T10:03:00")
        for task in (completed, archived, queued):
            repository.create(task, 10, TERMINAL_STATUSES)
        history_recorder = Mock()

        with (
            patch.object(app, "TASK_REPOSITORY", repository),
            patch.object(app, "record_task_history", history_recorder),
        ):
            app.repair_unarchived_task_history()

        history_recorder.assert_called_once()
        self.assertEqual(history_recorder.call_args.args[0]["id"], "completed")

    def test_successful_history_write_marks_terminal_task_archived(self):
        patches = self.archive_patches(save_succeeds=True)

        with (
            patches[0],
            patches[1],
            patches[2],
            patches[3],
            patches[4],
            patches[5],
            patches[6],
        ):
            manifest = app.record_task_history(self.task, {})

        self.assertIsNotNone(manifest)
        self.assertTrue(self.repository.get(self.task["id"])["history_archived_at"])

    def test_failed_history_write_remains_pending_for_repair(self):
        patches = self.archive_patches(save_succeeds=False)

        with (
            patches[0],
            patches[1],
            patches[2],
            patches[3],
            patches[4],
            patches[5],
            patches[6],
        ):
            manifest = app.record_task_history(self.task, {})

        self.assertIsNone(manifest)
        self.assertNotIn(
            "history_archived_at", self.repository.get(self.task["id"])
        )

    def test_archiving_never_deletes_active_history_when_record_count_grows(self):
        existing_record_count = 300
        oldest_directory = self.directory / "oldest-active-project"
        oldest_directory.mkdir()
        marker = oldest_directory / "keep.txt"
        marker.write_text("must remain", encoding="utf-8")
        records = [
            {
                "task_id": f"existing-{index:03d}",
                "status": "done",
                "record_state": app.HISTORY_RECORD_ACTIVE,
                "completed_at": f"{index:04d}",
                "artifact_dir": str(oldest_directory) if index == 0 else "",
            }
            for index in range(existing_record_count)
        ]
        history_data = {"records": records}

        with (
            patch.object(app, "TASK_REPOSITORY", self.repository),
            patch.object(app, "get_history_data", return_value=history_data),
            patch.object(
                app,
                "_history_record_dir",
                return_value=self.directory / "new-project-history",
            ),
            patch.object(
                app, "_copy_input_files_for_history", return_value=({}, [])
            ),
            patch.object(app, "_write_project_text_files"),
            patch.object(app, "_write_history_zip", return_value=""),
            patch.object(app, "save_history_data", return_value=True) as save_history,
        ):
            manifest = app.record_task_history(self.task, {})

        self.assertIsNotNone(manifest)
        self.assertTrue(marker.exists(), "archiving must never purge active artifacts")
        saved_records = save_history.call_args.args[0]["records"]
        self.assertEqual(len(saved_records), existing_record_count + 1)
        self.assertIn("existing-000", {item["task_id"] for item in saved_records})

    def test_clear_completed_tasks_removes_only_archived_done_tasks(self):
        archived = make_task("archived-done", "2026-07-29T10:01:00")
        archived.update(
            {"status": "done", "history_archived_at": "2026-07-29T10:02:00"}
        )
        self.repository.create(archived, 10, TERMINAL_STATUSES)
        for status in ("partial", "error", "cancelled", "expired"):
            task = make_task(f"{status}-task")
            task["status"] = status
            self.repository.create(task, 10, TERMINAL_STATUSES)

        with (
            patch.object(app, "TASK_REPOSITORY", self.repository),
            patch.object(app, "get_session_owner_id", return_value="test-workspace"),
        ):
            removed = app.clear_completed_tasks()

        self.assertEqual(removed, 1)
        self.assertIsNotNone(self.repository.get("history-task"))
        self.assertIsNone(self.repository.get("archived-done"))
        self.assertEqual(
            {task["status"] for task in self.repository.list()},
            {"done", "partial", "error", "cancelled", "expired"},
        )

    def test_purge_all_trash_includes_partial_results(self):
        history_data = {
            "records": [
                {
                    "task_id": "partial-result",
                    "status": "partial",
                    "record_state": app.HISTORY_RECORD_TRASHED,
                }
            ]
        }

        with (
            patch.object(app, "get_history_data", return_value=history_data),
            patch.object(app, "save_history_data", return_value=True) as save_history,
        ):
            removed = app.purge_all_trashed_history_records()

        self.assertEqual([record["task_id"] for record in removed], ["partial-result"])
        self.assertEqual(history_data["records"], [])
        save_history.assert_called_once_with(history_data)

    @unittest.skipUnless(
        "fork" in multiprocessing.get_all_start_methods(),
        "requires the multiprocessing fork start method",
    )
    def test_history_lock_serializes_cross_process_read_modify_write(self):
        history_path = self.directory / "shared-history.json"
        lock_path = self.directory / "shared-history.lock"
        history_path.write_text("[]", encoding="utf-8")
        context = multiprocessing.get_context("fork")
        processes = [
            context.Process(
                target=mutate_shared_history,
                args=(str(lock_path), str(history_path), task_id),
            )
            for task_id in ("task-a", "task-b")
        ]

        for process in processes:
            process.start()
        for process in processes:
            process.join(timeout=5)

        self.assertTrue(all(not process.is_alive() for process in processes))
        self.assertEqual([process.exitcode for process in processes], [0, 0])
        self.assertEqual(
            set(json.loads(history_path.read_text(encoding="utf-8"))),
            {"task-a", "task-b"},
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
