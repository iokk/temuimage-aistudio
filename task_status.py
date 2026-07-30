"""Shared task lifecycle status policy."""

from typing import Mapping


TASK_TERMINAL_STATUSES: frozenset[str] = frozenset(
    {"done", "partial", "error", "cancelled", "expired"}
)
TASK_COMPLETED_STATUSES: frozenset[str] = frozenset({"done"})
TASK_STATUS_TRANSITIONS: Mapping[str, frozenset[str]] = {
    "queued": frozenset({"running", "cancelled"}),
    "running": frozenset({"done", "partial", "error", "cancelled", "expired"}),
}
