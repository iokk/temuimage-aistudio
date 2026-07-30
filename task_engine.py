"""Background task orchestration independent from Streamlit rendering."""

from __future__ import annotations

import copy
import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Dict, Iterable, Mapping, Optional, Union

from task_status import TASK_TERMINAL_STATUSES
from task_store import DEFAULT_RUNNER_LEASE_SECONDS, SqliteTaskStore


DEFAULT_TERMINAL_STATUSES = TASK_TERMINAL_STATUSES


class TaskExecutionStopped(RuntimeError):
    """Raised when a handler no longer owns a running task."""


def _no_validation(_payload: dict) -> Iterable[str]:
    return ()


@dataclass(frozen=True)
class TaskOutcome:
    titles: list = field(default_factory=list)
    errors: list = field(default_factory=list)
    files: list = field(default_factory=list)
    item_results: list = field(default_factory=list)
    target_language: str = "zh"
    partial: bool = False
    metadata: dict = field(default_factory=dict)

    @classmethod
    def from_value(cls, value: Union["TaskOutcome", dict]) -> "TaskOutcome":
        if isinstance(value, cls):
            return value
        if not isinstance(value, dict):
            raise TypeError("任务执行器必须返回 TaskOutcome 或 dict")
        return cls(
            titles=copy.deepcopy(value.get("titles", []) or []),
            errors=copy.deepcopy(value.get("errors", []) or []),
            files=copy.deepcopy(value.get("files", []) or []),
            item_results=copy.deepcopy(value.get("item_results", []) or []),
            target_language=str(value.get("target_language") or "zh"),
            partial=bool(value.get("partial")),
            metadata=copy.deepcopy(value.get("metadata", {}) or {}),
        )

    def as_dict(self) -> dict:
        return {
            "titles": copy.deepcopy(self.titles),
            "errors": copy.deepcopy(self.errors),
            "files": copy.deepcopy(self.files),
            "item_results": copy.deepcopy(self.item_results),
            "target_language": self.target_language,
            "partial": self.partial,
            "metadata": copy.deepcopy(self.metadata),
        }


TaskExecutor = Callable[["TaskExecution"], Union[TaskOutcome, dict]]
TaskValidator = Callable[[dict], Iterable[str]]
TASK_CHECKPOINT_FIELDS = frozenset(
    {"progress", "result_files", "item_results", "errors"}
)


@dataclass(frozen=True)
class TaskHandler:
    execute: TaskExecutor
    validate_payload: TaskValidator = _no_validation


class TaskExecution:
    """Claim-scoped interface exposed to task handlers."""

    def __init__(self, repository: SqliteTaskStore, task: dict):
        self._repository = repository
        self.task = copy.deepcopy(task)
        self.task_id = str(task.get("id") or "")
        self.claim_token = str(task.get("claim_token") or "")

    def checkpoint(self, **updates) -> dict:
        unsupported_fields = sorted(set(updates) - TASK_CHECKPOINT_FIELDS)
        if unsupported_fields:
            raise ValueError(
                "checkpoint fields are not allowed: "
                + ", ".join(unsupported_fields)
            )
        changes = copy.deepcopy(updates)
        changes["updated_at"] = datetime.now().isoformat()
        persisted = self._repository.update(
            self.task_id,
            changes,
            expected_status="running",
            expected_claim_token=self.claim_token,
        )
        if not persisted:
            raise TaskExecutionStopped("任务执行权已失效")
        return persisted

    def raise_if_stopped(self) -> None:
        current = self._repository.get(self.task_id)
        if current and current.get("status") == "cancelled":
            raise TaskExecutionStopped("任务已取消")
        if (
            not current
            or current.get("status") != "running"
            or current.get("claim_token") != self.claim_token
        ):
            raise TaskExecutionStopped("任务执行权已失效")


class TaskEngine:
    """Claims, runs, checkpoints, and finalizes persistent background tasks."""

    def __init__(
        self,
        repository: SqliteTaskStore,
        handlers: Mapping[str, TaskHandler],
        *,
        runner_id: str,
        max_running: Union[int, Callable[[], int]],
        terminal_callback: Optional[Callable[[dict, dict], None]] = None,
        maintenance_callback: Optional[Callable[[], None]] = None,
        error_sanitizer: Callable[[str], str] = str,
        lease_seconds: int = DEFAULT_RUNNER_LEASE_SECONDS,
        heartbeat_seconds: int = 10,
        supervisor_interval_seconds: float = 5,
        orphan_error_message: str = "任务在后台中断，未自动重发以避免重复生成或计费。请手动重新提交。",
        logger: Optional[logging.Logger] = None,
    ):
        normalized_runner_id = str(runner_id or "").strip()
        if not normalized_runner_id:
            raise ValueError("runner id is required")
        self.repository = repository
        self._handlers: Dict[str, TaskHandler] = dict(handlers)
        self.runner_id = normalized_runner_id
        self._max_running = max_running
        self._terminal_callback = terminal_callback
        self._maintenance_callback = maintenance_callback
        self._error_sanitizer = error_sanitizer
        self._lease_seconds = max(5, int(lease_seconds))
        self._heartbeat_seconds = max(1, int(heartbeat_seconds))
        self._supervisor_interval_seconds = max(
            0.05, float(supervisor_interval_seconds)
        )
        self._orphan_error_message = orphan_error_message
        self._logger = logger or logging.getLogger(__name__)
        self._lock = threading.RLock()
        self._threads: Dict[str, threading.Thread] = {}
        self._supervisor: Optional[threading.Thread] = None
        self._supervisor_stop = threading.Event()
        self._supervisor_wake = threading.Event()

    def registered_types(self) -> tuple:
        return tuple(sorted(self._handlers))

    def validate(self, task_type: str, payload: dict) -> list:
        handler = self._handlers.get(str(task_type or ""))
        if not handler:
            return [f"不支持的任务类型：{task_type or 'unknown'}"]
        return [str(error) for error in handler.validate_payload(payload) if error]

    def start(self) -> threading.Thread:
        with self._lock:
            if self._supervisor and self._supervisor.is_alive():
                return self._supervisor
            self._supervisor_stop.clear()
            self._supervisor_wake.clear()
            self._supervisor = threading.Thread(
                target=self._supervisor_loop,
                daemon=True,
                name="tulite-task-supervisor",
            )
            self._supervisor.start()
            return self._supervisor

    def stop(self, timeout: float = 2) -> None:
        self._supervisor_stop.set()
        self._supervisor_wake.set()
        with self._lock:
            supervisor = self._supervisor
        if supervisor and supervisor.is_alive():
            supervisor.join(timeout=max(0, timeout))
        with self._lock:
            workers = list(self._threads.values())
        deadline = time.monotonic() + max(0, timeout)
        for worker in workers:
            if worker is threading.current_thread() or not worker.is_alive():
                continue
            worker.join(timeout=max(0, deadline - time.monotonic()))

    def schedule(self) -> None:
        self._recover_orphans()
        self._run_maintenance()
        max_running = self._max_running_count()
        with self._lock:
            self._threads = {
                task_id: thread
                for task_id, thread in self._threads.items()
                if thread.is_alive()
            }
            while len(self._threads) < max_running:
                task = self.repository.claim_next(
                    max_running=max_running,
                    runner_id=self.runner_id,
                    lease_seconds=self._lease_seconds,
                )
                if not task:
                    break
                task_id = str(task.get("id") or "")
                claim_token = str(task.get("claim_token") or "")
                worker = threading.Thread(
                    target=self.run_claimed,
                    args=(task_id, claim_token),
                    daemon=True,
                    name=f"tulite-task-{task_id}",
                )
                self._threads[task_id] = worker
                worker.start()

    def run_claimed(self, task_id: str, claim_token: str) -> None:
        task = None
        heartbeat_stop = threading.Event()
        heartbeat_thread = None
        try:
            task = self.repository.get(task_id)
            if (
                not task
                or task.get("status") != "running"
                or task.get("claim_token") != claim_token
                or task.get("runner_id") != self.runner_id
            ):
                return
            heartbeat_thread = threading.Thread(
                target=self._heartbeat_loop,
                args=(heartbeat_stop,),
                daemon=True,
                name=f"tulite-heartbeat-{task_id}",
            )
            heartbeat_thread.start()
            execution = TaskExecution(self.repository, task)
            execution.raise_if_stopped()
            handler = self._handlers.get(str(task.get("type") or ""))
            if not handler:
                raise ValueError(
                    f"不支持的任务类型：{task.get('type') or 'unknown'}"
                )
            outcome = TaskOutcome.from_value(handler.execute(execution))
            execution.raise_if_stopped()
            completed = self.repository.update(
                task_id,
                {
                    "status": "partial" if outcome.partial else "done",
                    "titles": copy.deepcopy(outcome.titles),
                    "errors": copy.deepcopy(outcome.errors),
                    "result_files": copy.deepcopy(outcome.files),
                    "item_results": copy.deepcopy(outcome.item_results),
                    "result_title_language": outcome.target_language,
                    "result_metadata": copy.deepcopy(outcome.metadata),
                    "updated_at": datetime.now().isoformat(),
                    "ended_at": datetime.now().isoformat(),
                },
                expected_status="running",
                expected_claim_token=claim_token,
            )
            if completed:
                self._notify_terminal(completed, outcome.as_dict())
        except TaskExecutionStopped:
            return
        except Exception as error:
            sanitized_error = self._error_sanitizer(str(error))
            safe_exception = RuntimeError(sanitized_error).with_traceback(
                error.__traceback__
            )
            self._logger.error(
                "task %s failed (type=%s)",
                task_id,
                (task or {}).get("type"),
                exc_info=(RuntimeError, safe_exception, error.__traceback__),
            )
            latest = self.repository.get(task_id) or task or {}
            if latest.get("status") == "cancelled":
                return
            errors = list(latest.get("errors") or [])
            if sanitized_error not in errors:
                errors.append(sanitized_error)
            failed = self.repository.update(
                task_id,
                {
                    "status": "error",
                    "errors": errors,
                    "updated_at": datetime.now().isoformat(),
                    "ended_at": datetime.now().isoformat(),
                },
                expected_status="running",
                expected_claim_token=claim_token,
            )
            if failed:
                self._notify_terminal(failed, self._task_snapshot(failed))
        finally:
            heartbeat_stop.set()
            if heartbeat_thread and heartbeat_thread.is_alive():
                heartbeat_thread.join(timeout=1)
            with self._lock:
                if self._threads.get(task_id) is threading.current_thread():
                    self._threads.pop(task_id, None)
            if not self._supervisor_stop.is_set():
                self._supervisor_wake.set()

    def _max_running_count(self) -> int:
        value = self._max_running() if callable(self._max_running) else self._max_running
        return max(1, int(value))

    def _recover_orphans(self) -> None:
        self.repository.heartbeat_runner(
            self.runner_id, lease_seconds=self._lease_seconds
        )
        with self._lock:
            active_ids = {
                task_id for task_id, thread in self._threads.items() if thread.is_alive()
            }
        recovered = self.repository.recover_orphaned_running(
            active_ids,
            self._orphan_error_message,
            runner_id=self.runner_id,
        )
        for task in recovered:
            self._notify_terminal(task, self._task_snapshot(task))

    def _run_maintenance(self) -> None:
        if not self._maintenance_callback:
            return
        try:
            self._maintenance_callback()
        except Exception:
            self._logger.exception("task maintenance cycle failed")

    def _heartbeat_loop(self, stop_event: threading.Event) -> None:
        while not stop_event.wait(self._heartbeat_seconds):
            try:
                self.repository.heartbeat_runner(
                    self.runner_id, lease_seconds=self._lease_seconds
                )
            except Exception:
                self._logger.exception(
                    "task runner heartbeat failed (runner_id=%s)", self.runner_id
                )

    def _supervisor_loop(self) -> None:
        while not self._supervisor_stop.is_set():
            try:
                self.schedule()
            except Exception:
                self._logger.exception("task supervisor scheduling cycle failed")
            self._supervisor_wake.wait(self._supervisor_interval_seconds)
            self._supervisor_wake.clear()
            if self._supervisor_stop.is_set():
                break

    def _notify_terminal(self, task: dict, result: dict) -> None:
        if not self._terminal_callback:
            return
        try:
            self._terminal_callback(copy.deepcopy(task), copy.deepcopy(result))
        except Exception:
            self._logger.exception(
                "task terminal callback failed (task_id=%s)", task.get("id")
            )

    @staticmethod
    def _task_snapshot(task: dict) -> dict:
        return {
            "titles": copy.deepcopy(task.get("titles", []) or []),
            "errors": copy.deepcopy(task.get("errors", []) or []),
            "files": copy.deepcopy(task.get("result_files", []) or []),
            "item_results": copy.deepcopy(task.get("item_results", []) or []),
            "target_language": task.get("result_title_language") or "zh",
            "metadata": copy.deepcopy(task.get("result_metadata", {}) or {}),
        }
