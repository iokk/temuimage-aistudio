import tempfile
import threading
import time
import unittest
from pathlib import Path

from task_engine import TaskEngine, TaskExecution, TaskHandler, TaskOutcome
from task_store import SqliteTaskStore


TERMINAL_STATUSES = {"done", "partial", "error", "cancelled", "expired"}


def make_task(task_id: str, task_type: str = "example") -> dict:
    now = "2026-07-29T10:00:00"
    return {
        "id": task_id,
        "type": task_type,
        "status": "queued",
        "owner_id": "test-workspace",
        "created_at": now,
        "updated_at": now,
        "payload": {"value": task_id},
        "errors": [],
        "result_files": [],
    }


def wait_for(predicate, timeout: float = 2) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return bool(predicate())


class TaskEngineTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.repository = SqliteTaskStore(
            Path(self.temporary_directory.name) / "tasks.sqlite3"
        )
        self.terminal_events = []
        self.engines = []

    def tearDown(self):
        for engine in self.engines:
            engine.stop()

    def make_engine(self, handlers, **overrides):
        options = {
            "runner_id": "test-runner",
            "max_running": 1,
            "terminal_callback": lambda task, result: self.terminal_events.append(
                (task, result)
            ),
            "supervisor_interval_seconds": 0.01,
            "heartbeat_seconds": 1,
            "lease_seconds": 5,
        }
        options.update(overrides)
        engine = TaskEngine(self.repository, handlers, **options)
        self.engines.append(engine)
        return engine

    def enqueue(self, task):
        return self.repository.create(task, 20, TERMINAL_STATUSES)

    def test_supervisor_runs_registered_handler_without_a_ui_rerun(self):
        def execute(execution):
            execution.checkpoint(
                progress={"done": 1, "total": 1},
                result_files=["checkpoint.png"],
            )
            return TaskOutcome(
                files=["checkpoint.png"],
                item_results=[{"status": "done", "file_path": "checkpoint.png"}],
                metadata={"kind": "example"},
            )

        self.enqueue(make_task("background-task"))
        engine = self.make_engine({"example": TaskHandler(execute)})

        first_supervisor = engine.start()
        second_supervisor = engine.start()

        self.assertIs(first_supervisor, second_supervisor)
        self.assertTrue(
            wait_for(
                lambda: self.repository.get("background-task")["status"] == "done"
            )
        )
        persisted = self.repository.get("background-task")
        self.assertEqual(persisted["result_files"], ["checkpoint.png"])
        self.assertEqual(persisted["result_metadata"], {"kind": "example"})
        self.assertEqual(len(self.terminal_events), 1)

    def test_checkpoint_rejects_lifecycle_and_identity_fields(self):
        self.enqueue(make_task("guarded-checkpoint"))
        claimed = self.repository.claim_next(1, "test-runner")
        execution = TaskExecution(self.repository, claimed)

        with self.assertRaisesRegex(ValueError, "owner_id, status"):
            execution.checkpoint(status="done", owner_id="other-workspace")

        persisted = self.repository.get("guarded-checkpoint")
        self.assertEqual(persisted["status"], "running")
        self.assertEqual(persisted["owner_id"], "test-workspace")

    def test_checkpoint_rejects_each_privileged_field_before_repository_mutation(self):
        class RepositorySpy:
            def __init__(self):
                self.updates = []

            def update(self, *args, **kwargs):
                self.updates.append((args, kwargs))

        claimed_task = {
            "id": "guarded-checkpoint",
            "status": "running",
            "claim_token": "current-claim",
        }
        prohibited_updates = {
            "id": "other-id",
            "type": "other-type",
            "owner_id": "other-owner",
            "status": "done",
            "claim_token": "other-claim",
            "runner_id": "other-runner",
            "available_at": "2026-07-30T12:00:00+00:00",
            "payload": {"prompt": "mutated"},
        }

        for field, value in prohibited_updates.items():
            with self.subTest(field=field):
                repository = RepositorySpy()
                execution = TaskExecution(repository, claimed_task)

                with self.assertRaisesRegex(ValueError, field):
                    execution.checkpoint(**{field: value})

                self.assertEqual(repository.updates, [])

    def test_worker_completion_wakes_supervisor_for_the_next_queued_task(self):
        executed = []

        def execute(execution):
            executed.append(execution.task_id)
            return TaskOutcome()

        self.enqueue(make_task("first-task"))
        self.enqueue(make_task("second-task"))
        engine = self.make_engine(
            {"example": TaskHandler(execute)},
            supervisor_interval_seconds=30,
        )

        engine.start()

        self.assertTrue(
            wait_for(
                lambda: self.repository.get("first-task")["status"] == "done"
                and self.repository.get("second-task")["status"] == "done",
                timeout=1,
            )
        )
        self.assertEqual(executed, ["first-task", "second-task"])

    def test_unknown_task_type_fails_without_calling_registered_handler(self):
        executor_called = threading.Event()

        def execute(_execution):
            executor_called.set()
            return TaskOutcome()

        self.enqueue(make_task("unknown-task", "future-type"))
        engine = self.make_engine({"example": TaskHandler(execute)})

        engine.start()

        self.assertTrue(
            wait_for(lambda: self.repository.get("unknown-task")["status"] == "error")
        )
        task = self.repository.get("unknown-task")
        self.assertFalse(executor_called.is_set())
        self.assertTrue(any("不支持的任务类型" in error for error in task["errors"]))

    def test_handler_exception_is_sanitized_before_logging_or_persistence(self):
        opaque_secret = "opaque-task-secret-123"

        def execute(_execution):
            raise RuntimeError(f"upstream echoed {opaque_secret}")

        self.enqueue(make_task("secret-failure"))
        claimed = self.repository.claim_next(1, "test-runner")
        engine = self.make_engine(
            {"example": TaskHandler(execute)},
            error_sanitizer=lambda message: message.replace(
                opaque_secret, "[REDACTED]"
            ),
        )

        with self.assertLogs("task_engine", level="ERROR") as captured:
            engine.run_claimed("secret-failure", claimed["claim_token"])

        log_output = "\n".join(captured.output)
        persisted = self.repository.get("secret-failure")
        self.assertNotIn(opaque_secret, log_output)
        self.assertIn("[REDACTED]", log_output)
        self.assertNotIn(opaque_secret, " ".join(persisted["errors"]))
        self.assertIn("[REDACTED]", " ".join(persisted["errors"]))

    def test_cancellation_wins_over_a_late_handler_result(self):
        started = threading.Event()
        release = threading.Event()

        def execute(_execution):
            started.set()
            release.wait(2)
            return TaskOutcome(files=["late.png"])

        self.enqueue(make_task("cancelled-task"))
        engine = self.make_engine({"example": TaskHandler(execute)})
        engine.start()
        self.assertTrue(started.wait(1))

        cancelled = self.repository.update(
            "cancelled-task",
            {"status": "cancelled"},
            expected_status="running",
        )
        release.set()

        self.assertIsNotNone(cancelled)
        self.assertTrue(
            wait_for(
                lambda: self.repository.get("cancelled-task")["status"]
                == "cancelled"
            )
        )
        time.sleep(0.05)
        self.assertEqual(self.repository.get("cancelled-task")["result_files"], [])

    def test_handler_registry_validates_payload_at_the_execution_seam(self):
        engine = self.make_engine(
            {
                "example": TaskHandler(
                    lambda _execution: TaskOutcome(),
                    validate_payload=lambda payload: (
                        [] if payload.get("prompt") else ["缺少 prompt"]
                    ),
                )
            }
        )

        self.assertEqual(engine.registered_types(), ("example",))
        self.assertEqual(engine.validate("example", {}), ["缺少 prompt"])
        self.assertEqual(engine.validate("example", {"prompt": "ok"}), [])
        self.assertEqual(
            engine.validate("missing", {}), ["不支持的任务类型：missing"]
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
