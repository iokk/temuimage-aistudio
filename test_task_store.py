import json
import sqlite3
import tempfile
import threading
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from task_store import SCHEMA_VERSION, SqliteTaskStore, TaskCapacityError


TERMINAL_STATUSES = {"done", "partial", "error", "cancelled", "expired"}


def make_task(task_id, status="queued", created_at="2026-07-29T10:00:00", **extra):
    task = {
        "id": task_id,
        "type": "text_to_image",
        "status": status,
        "owner_id": "installation-owner",
        "created_at": created_at,
        "updated_at": created_at,
        "payload": {"prompt": f"prompt for {task_id}"},
    }
    task.update(extra)
    return task


class SqliteTaskStoreTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.directory = Path(self.temporary_directory.name)
        self.database_path = self.directory / "tasks.sqlite3"

    def make_store(self, legacy_json_path=None):
        return SqliteTaskStore(
            self.database_path,
            legacy_json_path=legacy_json_path,
        )

    def create_version_one_database(self, task):
        with sqlite3.connect(str(self.database_path)) as connection:
            connection.executescript(
                """
                CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE tasks (
                    id TEXT PRIMARY KEY,
                    task_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    owner_id TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    document TEXT NOT NULL
                );
                CREATE TABLE task_runners (
                    id TEXT PRIMARY KEY,
                    heartbeat_at TEXT NOT NULL,
                    lease_expires_at TEXT NOT NULL
                );
                """
            )
            connection.execute(
                "INSERT INTO metadata(key, value) VALUES('schema_version', '1')"
            )
            connection.execute(
                "INSERT INTO tasks(id, task_type, status, owner_id, created_at, updated_at, document) "
                "VALUES(?, ?, ?, ?, ?, ?, ?)",
                (
                    task["id"],
                    task["type"],
                    task["status"],
                    task["owner_id"],
                    task["created_at"],
                    task["updated_at"],
                    json.dumps(task),
                ),
            )

    def test_tasks_persist_across_store_instances(self):
        first_store = self.make_store()
        original = make_task(
            "persistent-task",
            summary="A persisted task",
            item_results=[{"status": "done", "file_path": "result.png"}],
        )
        first_store.create(original, max_tasks=10, terminal_statuses=TERMINAL_STATUSES)

        second_store = self.make_store()

        self.assertEqual(second_store.get(original["id"]), original)
        self.assertEqual(second_store.list(), [original])

    def test_workspace_id_is_stable_across_store_instances(self):
        first_store = self.make_store()
        workspace_id = first_store.get_or_create_workspace_id("preferred-owner")

        second_store = self.make_store()

        self.assertEqual(workspace_id, "preferred-owner")
        self.assertEqual(second_store.get_or_create_workspace_id("ignored"), workspace_id)

    def test_capacity_prunes_oldest_archived_terminal_task_before_creating(self):
        store = self.make_store()
        archived = make_task(
            "archived",
            status="done",
            history_archived_at="2026-07-29T09:30:00",
        )
        store.create(archived, 1, TERMINAL_STATUSES)
        store.create(
            make_task("replacement", created_at="2026-07-29T11:00:00"),
            1,
            TERMINAL_STATUSES,
        )

        self.assertIsNone(store.get("archived"))

    def test_invalid_replacement_rolls_back_archived_capacity_pruning(self):
        store = self.make_store()
        archived = make_task(
            "archived",
            status="done",
            history_archived_at="2026-07-29T09:30:00",
        )
        store.create(archived, 1, TERMINAL_STATUSES)

        with self.assertRaisesRegex(ValueError, "available_at"):
            store.create(
                make_task("invalid-replacement", available_at="not-a-timestamp"),
                1,
                TERMINAL_STATUSES,
            )

        self.assertEqual(store.get("archived"), archived)
        self.assertIsNone(store.get("invalid-replacement"))

    def test_capacity_never_prunes_unarchived_terminal_task(self):
        store = self.make_store()
        pending_archive = make_task("pending-archive", status="error")
        store.create(pending_archive, 1, TERMINAL_STATUSES)

        with self.assertRaises(TaskCapacityError):
            store.create(make_task("replacement"), 1, TERMINAL_STATUSES)

        self.assertEqual(store.get("pending-archive"), pending_archive)

    def test_capacity_rejects_new_task_when_only_active_tasks_fill_store(self):
        store = self.make_store()
        queued = make_task("queued", status="queued")
        running = make_task(
            "running", status="running", created_at="2026-07-29T10:01:00"
        )
        store.create(queued, 2, TERMINAL_STATUSES)
        store.create(running, 2, TERMINAL_STATUSES)

        with self.assertRaises(TaskCapacityError):
            store.create(
                make_task("rejected", created_at="2026-07-29T10:02:00"),
                2,
                TERMINAL_STATUSES,
            )

        self.assertEqual(
            {task["id"] for task in store.list()},
            {"queued", "running"},
        )

    def test_capacity_is_enforced_per_owner_scope(self):
        store = self.make_store()
        owner_a = make_task("owner-a-task", owner_id="owner-a")
        owner_b = make_task("owner-b-task", owner_id="owner-b")

        store.create(owner_a, 1, TERMINAL_STATUSES)
        store.create(owner_b, 1, TERMINAL_STATUSES)

        self.assertEqual(
            {task["id"] for task in store.list()},
            {"owner-a-task", "owner-b-task"},
        )

    def test_create_reuses_existing_task_for_the_same_owner_and_submission(self):
        store = self.make_store()
        first = make_task(
            "first-task",
            owner_id="owner-a",
            submission_id="submission-1",
        )
        duplicate = make_task(
            "duplicate-task",
            owner_id="owner-a",
            submission_id="submission-1",
        )

        created = store.create(first, 10, TERMINAL_STATUSES)
        replayed = store.create(duplicate, 10, TERMINAL_STATUSES)

        self.assertEqual(replayed, created)
        self.assertEqual([task["id"] for task in store.list()], ["first-task"])

        other_owner = store.create(
            make_task(
                "other-owner-task",
                owner_id="owner-b",
                submission_id="submission-1",
            ),
            10,
            TERMINAL_STATUSES,
        )
        self.assertEqual(other_owner["id"], "other-owner-task")
        self.assertEqual(len(store.list()), 2)

    def test_concurrent_create_with_one_submission_returns_one_task(self):
        stores = [self.make_store(), self.make_store()]
        barrier = threading.Barrier(3)
        results = []
        failures = []

        def create_submission(store, index):
            try:
                barrier.wait()
                results.append(
                    store.create(
                        make_task(
                            f"task-{index}",
                            owner_id="owner-a",
                            submission_id="submission-race",
                        ),
                        10,
                        TERMINAL_STATUSES,
                    )
                )
            except BaseException as error:
                failures.append(error)

        threads = [
            threading.Thread(target=create_submission, args=(store, index))
            for index, store in enumerate(stores)
        ]
        for thread in threads:
            thread.start()
        barrier.wait()
        for thread in threads:
            thread.join(timeout=10)

        self.assertTrue(all(not thread.is_alive() for thread in threads))
        self.assertEqual(failures, [])
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["id"], results[1]["id"])
        self.assertEqual(len(self.make_store().list()), 1)

    def test_owner_scope_is_enforced_by_queries_updates_and_cleanup(self):
        store = self.make_store()
        tasks = [
            make_task("owner-a-done", status="done", owner_id="owner-a"),
            make_task(
                "owner-b-done",
                status="done",
                owner_id="owner-b",
                created_at="2026-07-29T10:01:00",
            ),
            make_task(
                "legacy-unowned",
                status="done",
                owner_id="",
                created_at="2026-07-29T10:02:00",
            ),
        ]
        for task in tasks:
            store.create(task, 10, TERMINAL_STATUSES)

        visible = store.list(scope_owner_id="owner-a", include_unowned=True)
        rejected = store.update(
            "owner-b-done",
            {"summary": "must not change"},
            scope_owner_id="owner-a",
        )
        removed = store.clear_terminal(
            TERMINAL_STATUSES,
            scope_owner_id="owner-a",
            include_unowned=True,
        )

        self.assertEqual(
            {task["id"] for task in visible},
            {"owner-a-done", "legacy-unowned"},
        )
        self.assertIsNone(
            store.get("owner-b-done", scope_owner_id="owner-a")
        )
        self.assertIsNone(rejected)
        self.assertEqual(removed, 2)
        self.assertIsNotNone(store.get("owner-b-done"))

    def test_expected_status_allows_only_one_concurrent_claim(self):
        setup_store = self.make_store()
        setup_store.create(
            make_task("claim-once"),
            max_tasks=10,
            terminal_statuses=TERMINAL_STATUSES,
        )
        stores = [self.make_store(), self.make_store()]
        barrier = threading.Barrier(3)
        results = []
        failures = []

        def claim(store, worker_id):
            try:
                barrier.wait()
                result = store.update(
                    "claim-once",
                    {"status": "running", "worker_id": worker_id},
                    expected_status="queued",
                )
                results.append(result)
            except BaseException as error:
                failures.append(error)

        threads = [
            threading.Thread(target=claim, args=(store, f"worker-{index}"))
            for index, store in enumerate(stores)
        ]
        for thread in threads:
            thread.start()
        barrier.wait()
        for thread in threads:
            thread.join(timeout=10)

        self.assertTrue(all(not thread.is_alive() for thread in threads))
        self.assertEqual(failures, [])
        successful_claims = [result for result in results if result is not None]
        self.assertEqual(len(successful_claims), 1)
        self.assertEqual(setup_store.get("claim-once")["status"], "running")
        self.assertEqual(
            setup_store.get("claim-once")["worker_id"],
            successful_claims[0]["worker_id"],
        )

    def test_claim_next_uses_queue_order_assigns_claim_identity_and_honors_limit(self):
        store = self.make_store()
        tasks = [
            make_task(
                "already-running",
                status="running",
                created_at="2026-07-29T08:00:00",
            ),
            make_task("z-newer", created_at="2026-07-29T10:00:00"),
            make_task("b-oldest", created_at="2026-07-29T09:00:00"),
            make_task("a-oldest", created_at="2026-07-29T09:00:00"),
        ]
        for task in tasks:
            store.create(task, 10, TERMINAL_STATUSES)
        claimed_at = datetime(2026, 7, 29, 12, 0, 0)

        claimed = store.claim_next(
            max_running=2,
            runner_id="scheduler-a",
            now=claimed_at,
        )

        self.assertEqual(claimed["id"], "a-oldest")
        self.assertEqual(claimed["status"], "running")
        self.assertEqual(claimed["runner_id"], "scheduler-a")
        self.assertRegex(claimed["claim_token"], r"^[0-9a-f]{32}$")
        self.assertEqual(claimed["started_at"], claimed_at.isoformat())
        self.assertEqual(claimed["updated_at"], claimed_at.isoformat())
        self.assertIsNone(
            store.claim_next(max_running=2, runner_id="scheduler-b")
        )
        self.assertEqual(store.get("b-oldest")["status"], "queued")

    def test_claim_next_prioritizes_ready_tasks_without_claiming_delayed_work(self):
        store = self.make_store()
        tasks = [
            make_task(
                "normal-ready",
                created_at="2026-07-29T09:00:00",
                priority=0,
            ),
            make_task(
                "urgent-ready",
                created_at="2026-07-29T10:00:00",
                priority=10,
            ),
            make_task(
                "urgent-delayed",
                created_at="2026-07-29T08:00:00",
                priority=100,
                available_at="2026-07-29T13:00:00",
            ),
        ]
        for task in tasks:
            store.create(task, 10, TERMINAL_STATUSES)

        claimed = store.claim_next(
            1,
            "priority-runner",
            now=datetime(2026, 7, 29, 12, 0, 0),
        )

        self.assertEqual(claimed["id"], "urgent-ready")
        self.assertEqual(store.get("urgent-delayed")["status"], "queued")

    def test_claim_next_compares_available_at_as_an_absolute_instant(self):
        store = self.make_store()
        future = make_task(
            "future-offset",
            available_at="2026-07-29T04:30:00+00:00",
        )
        store.create(future, 10, TERMINAL_STATUSES)
        now = datetime(
            2026,
            7,
            29,
            12,
            0,
            tzinfo=timezone(timedelta(hours=8)),
        )

        claimed = store.claim_next(1, "timezone-runner", now=now)

        self.assertIsNone(claimed)
        self.assertEqual(store.get("future-offset")["status"], "queued")

    def test_create_rejects_invalid_available_at(self):
        store = self.make_store()

        with self.assertRaisesRegex(ValueError, "available_at"):
            store.create(
                make_task("invalid-schedule", available_at="not-a-timestamp"),
                10,
                TERMINAL_STATUSES,
            )

        self.assertIsNone(store.get("invalid-schedule"))

    def test_concurrent_claim_next_never_exceeds_global_running_limit(self):
        setup_store = self.make_store()
        for index in range(3):
            setup_store.create(
                make_task(
                    f"queued-{index}",
                    created_at=f"2026-07-29T10:0{index}:00",
                ),
                max_tasks=10,
                terminal_statuses=TERMINAL_STATUSES,
            )
        stores = [self.make_store(), self.make_store()]
        barrier = threading.Barrier(3)
        results = []
        failures = []

        def claim(store, runner_id):
            try:
                barrier.wait()
                results.append(store.claim_next(1, runner_id))
            except BaseException as error:
                failures.append(error)

        threads = [
            threading.Thread(target=claim, args=(store, f"runner-{index}"))
            for index, store in enumerate(stores)
        ]
        for thread in threads:
            thread.start()
        barrier.wait()
        for thread in threads:
            thread.join(timeout=10)

        self.assertTrue(all(not thread.is_alive() for thread in threads))
        self.assertEqual(failures, [])
        self.assertEqual(len([result for result in results if result]), 1)
        persisted = setup_store.list()
        self.assertEqual(
            len([task for task in persisted if task["status"] == "running"]),
            1,
        )
        self.assertEqual(
            len([task for task in persisted if task["status"] == "queued"]),
            2,
        )

    def test_worker_update_requires_current_claim_token(self):
        store = self.make_store()
        store.create(make_task("token-guarded"), 10, TERMINAL_STATUSES)
        claimed = store.claim_next(1, "runner-a")

        rejected = store.update(
            claimed["id"],
            {"status": "done", "result": "must not persist"},
            expected_status="running",
            expected_claim_token="stale-or-wrong-token",
        )

        self.assertIsNone(rejected)
        self.assertEqual(store.get(claimed["id"]), claimed)
        completed = store.update(
            claimed["id"],
            {"status": "done", "result": "accepted"},
            expected_status="running",
            expected_claim_token=claimed["claim_token"],
        )
        self.assertEqual(completed["status"], "done")
        self.assertEqual(completed["result"], "accepted")

    def test_cancelled_task_cannot_be_overwritten_by_claimed_worker(self):
        store = self.make_store()
        store.create(make_task("cancel-race"), 10, TERMINAL_STATUSES)
        claimed = store.claim_next(1, "runner-a")
        cancelled = store.update(
            claimed["id"],
            {"status": "cancelled", "ended_at": "2026-07-29T12:10:00"},
            expected_status=("queued", "running"),
        )

        late_completion = store.update(
            claimed["id"],
            {"status": "done", "result": "late worker result"},
            expected_status="running",
            expected_claim_token=claimed["claim_token"],
        )

        self.assertIsNone(late_completion)
        self.assertEqual(store.get(claimed["id"]), cancelled)
        self.assertNotIn("result", store.get(claimed["id"]))

    def test_terminal_statuses_cannot_transition_again(self):
        transition_attempts = {
            "done": "error",
            "partial": "done",
            "error": "running",
            "cancelled": "running",
            "expired": "queued",
        }
        for index, (terminal_status, next_status) in enumerate(
            transition_attempts.items()
        ):
            with self.subTest(status=terminal_status, next_status=next_status):
                store = self.make_store()
                task = make_task(
                    f"terminal-{index}",
                    status=terminal_status,
                    created_at=f"2026-07-29T11:0{index}:00",
                )
                store.create(task, 10, TERMINAL_STATUSES)

                result = store.update(
                    task["id"],
                    {"status": next_status, "result": "must not persist"},
                    expected_status=terminal_status,
                )

                self.assertIsNone(result)
                self.assertEqual(store.get(task["id"]), task)

    def test_queued_task_survives_reopening_database(self):
        first_store = self.make_store()
        queued = make_task("queued-after-restart")
        first_store.create(queued, 10, TERMINAL_STATUSES)

        reopened_store = SqliteTaskStore(Path(str(self.database_path)))

        self.assertEqual(reopened_store.get(queued["id"])["status"], "queued")

    def test_recovery_expires_only_orphaned_running_tasks(self):
        store = self.make_store()
        active = make_task("active-running", status="running")
        orphaned = make_task(
            "orphaned-running",
            status="running",
            created_at="2026-07-29T10:01:00",
            errors=["earlier warning"],
        )
        queued = make_task(
            "still-queued", status="queued", created_at="2026-07-29T10:02:00"
        )
        for task in (active, orphaned, queued):
            store.create(task, 10, TERMINAL_STATUSES)
        recovered_at = datetime(2026, 7, 29, 12, 30, 0)

        recovered = store.recover_orphaned_running(
            active_task_ids={active["id"]},
            error_message="Worker stopped before completion.",
            now=recovered_at,
        )

        self.assertEqual([task["id"] for task in recovered], [orphaned["id"]])
        recovered_task = store.get(orphaned["id"])
        self.assertEqual(recovered_task["status"], "expired")
        self.assertEqual(
            recovered_task["errors"],
            ["earlier warning", "Worker stopped before completion."],
        )
        self.assertEqual(recovered_task["updated_at"], recovered_at.isoformat())
        self.assertEqual(recovered_task["ended_at"], recovered_at.isoformat())
        self.assertEqual(store.get(active["id"])["status"], "running")
        self.assertEqual(store.get(queued["id"])["status"], "queued")

    def test_recovery_does_not_expire_another_runner_task(self):
        store = self.make_store()
        local = make_task("local-running", status="running", runner_id="runner-a")
        remote = make_task(
            "remote-running",
            status="running",
            runner_id="runner-b",
            created_at="2026-07-29T10:01:00",
        )
        for task in (local, remote):
            store.create(task, 10, TERMINAL_STATUSES)
        store.heartbeat_runner("runner-b", lease_seconds=60)

        recovered = store.recover_orphaned_running(
            active_task_ids=set(),
            error_message="Worker stopped.",
            runner_id="runner-a",
        )

        self.assertEqual([task["id"] for task in recovered], [local["id"]])
        self.assertEqual(store.get(local["id"])["status"], "expired")
        self.assertEqual(store.get(remote["id"])["status"], "running")

    def test_foreign_runner_task_expires_only_after_its_lease(self):
        store = self.make_store()
        task = make_task("leased-running", status="running", runner_id="runner-a")
        store.create(task, 10, TERMINAL_STATUSES)
        heartbeat_at = datetime(2026, 7, 29, 12, 0, 0)
        store.heartbeat_runner("runner-a", lease_seconds=30, now=heartbeat_at)

        still_live = store.recover_orphaned_running(
            active_task_ids=set(),
            error_message="Worker stopped.",
            runner_id="runner-b",
            now=datetime(2026, 7, 29, 12, 0, 29),
        )
        expired = store.recover_orphaned_running(
            active_task_ids=set(),
            error_message="Worker stopped.",
            runner_id="runner-b",
            now=datetime(2026, 7, 29, 12, 0, 31),
        )

        self.assertEqual(still_live, [])
        self.assertEqual([item["id"] for item in expired], [task["id"]])
        self.assertEqual(store.get(task["id"])["status"], "expired")

    def test_prunes_only_runner_leases_older_than_retention_window(self):
        store = self.make_store()
        stale_heartbeat = datetime(2026, 7, 29, 10, 0, 0)
        recent_heartbeat = datetime(2026, 7, 29, 11, 45, 0)
        store.heartbeat_runner(
            "stale-runner",
            lease_seconds=30,
            now=stale_heartbeat,
        )
        store.heartbeat_runner(
            "recent-runner",
            lease_seconds=30,
            now=recent_heartbeat,
        )

        pruned = store.prune_expired_runners(
            now=datetime(2026, 7, 29, 12, 0, 0),
            retention_seconds=60 * 60,
        )

        with sqlite3.connect(str(self.database_path)) as connection:
            runner_ids = {
                row[0]
                for row in connection.execute(
                    "SELECT id FROM task_runners ORDER BY id"
                ).fetchall()
            }
        self.assertEqual(pruned, 1)
        self.assertEqual(runner_ids, {"recent-runner"})

    def test_legacy_tasks_json_is_migrated_once(self):
        legacy_path = self.directory / "tasks.json"
        legacy_tasks = [
            make_task("legacy-queued", status="queued"),
            make_task(
                "legacy-done",
                status="done",
                created_at="2026-07-29T09:00:00",
            ),
        ]
        legacy_path.write_text(
            json.dumps({"schema_version": 1, "tasks": legacy_tasks}),
            encoding="utf-8",
        )

        migrated_store = self.make_store(legacy_json_path=legacy_path)
        reopened_store = self.make_store(legacy_json_path=legacy_path)

        self.assertEqual(
            {task["id"]: task for task in migrated_store.list()},
            {task["id"]: task for task in legacy_tasks},
        )
        self.assertEqual(len(reopened_store.list()), len(legacy_tasks))

        migrated_store.clear_terminal(TERMINAL_STATUSES)
        migrated_store.update(
            "legacy-queued", {"status": "cancelled"}, expected_status="queued"
        )
        migrated_store.clear_terminal(TERMINAL_STATUSES)

        empty_reopened_store = self.make_store(legacy_json_path=legacy_path)
        self.assertEqual(empty_reopened_store.list(), [])

    def test_legacy_import_quarantines_invalid_schedule_without_blocking_siblings(self):
        legacy_path = self.directory / "tasks.json"
        valid = make_task("legacy-valid", available_at="2030-07-29T09:30:00+00:00")
        malformed = make_task("legacy-malformed", available_at="not-a-timestamp")
        legacy_path.write_text(
            json.dumps({"schema_version": 1, "tasks": [valid, malformed]}),
            encoding="utf-8",
        )

        migrated = self.make_store(legacy_json_path=legacy_path)

        self.assertEqual(migrated.get("legacy-valid")["id"], "legacy-valid")
        quarantined = migrated.get("legacy-malformed")
        self.assertEqual(
            quarantined["available_at"],
            "9999-12-31T23:59:59.999999+00:00",
        )
        self.assertIsNone(
            migrated.claim_next(
                1, "legacy-import-runner", now=datetime(2026, 7, 30, 12, 0, 0)
            )
        )
        self.assertEqual(
            migrated.update(
                "legacy-malformed", {"status": "cancelled"}, expected_status="queued"
            )["status"],
            "cancelled",
        )

    def test_initialization_quarantines_corrupt_document_without_skipping_valid_rows(self):
        store = self.make_store()
        corrupt = make_task("corrupt-document")
        valid = make_task("valid-document", available_at="2026-07-29T09:30:00+00:00")
        store.create(corrupt, 10, TERMINAL_STATUSES)
        store.create(valid, 10, TERMINAL_STATUSES)
        with sqlite3.connect(str(self.database_path)) as connection:
            connection.execute(
                "UPDATE tasks SET document = ?, available_at = '' WHERE id = ?",
                ("{not valid json", "corrupt-document"),
            )
            connection.execute(
                "UPDATE tasks SET available_at = '' WHERE id = ?",
                ("valid-document",),
            )

        self.make_store()

        with sqlite3.connect(str(self.database_path)) as connection:
            corrupt_row = connection.execute(
                "SELECT available_at, document FROM tasks WHERE id = ?",
                ("corrupt-document",),
            ).fetchone()
            valid_index = connection.execute(
                "SELECT available_at FROM tasks WHERE id = ?", ("valid-document",)
            ).fetchone()[0]
        self.assertEqual(corrupt_row[0], "9999-12-31T23:59:59.999999+00:00")
        self.assertEqual(corrupt_row[1], "{not valid json")
        self.assertEqual(valid_index, "2026-07-29T09:30:00.000000+00:00")

    def test_version_one_database_is_migrated_transactionally(self):
        legacy_task = make_task("schema-v1-task")
        self.create_version_one_database(legacy_task)

        migrated = self.make_store()

        self.assertEqual(migrated.get("schema-v1-task"), legacy_task)
        self.assertEqual(int(migrated.get_metadata("schema_version")), SCHEMA_VERSION)
        with sqlite3.connect(str(self.database_path)) as connection:
            columns = {
                row[1] for row in connection.execute("PRAGMA table_info(tasks)")
            }
            indexes = {
                row[1] for row in connection.execute("PRAGMA index_list(tasks)")
            }
        self.assertIn("priority", columns)
        self.assertIn("available_at", columns)
        self.assertIn("idx_tasks_claim_order", indexes)

    def test_version_one_migration_indexes_document_schedule_in_utc(self):
        legacy_task = make_task(
            "legacy-scheduled",
            available_at="2026-07-29T04:30:00+00:00",
        )
        self.create_version_one_database(legacy_task)

        migrated = self.make_store()
        now = datetime(
            2026,
            7,
            29,
            12,
            0,
            tzinfo=timezone(timedelta(hours=8)),
        )

        self.assertIsNone(migrated.claim_next(1, "migration-runner", now=now))
        with sqlite3.connect(str(self.database_path)) as connection:
            indexed_value = connection.execute(
                "SELECT available_at FROM tasks WHERE id = 'legacy-scheduled'"
            ).fetchone()[0]
        self.assertEqual(indexed_value, "2026-07-29T04:30:00.000000+00:00")

    def test_version_one_migration_quarantines_invalid_schedule(self):
        legacy_task = make_task(
            "legacy-invalid-schedule",
            available_at="not-a-timestamp",
        )
        self.create_version_one_database(legacy_task)

        migrated = self.make_store()

        self.assertIsNone(
            migrated.claim_next(
                1,
                "migration-runner",
                now=datetime(2026, 7, 29, 12, 0, 0),
            )
        )
        self.assertEqual(
            migrated.get("legacy-invalid-schedule")["available_at"],
            "9999-12-31T23:59:59.999999+00:00",
        )


if __name__ == "__main__":
    unittest.main()
