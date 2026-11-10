"""Append-only JSONL audit logging for planning decisions.

Purpose: persist each node's observable output for demo and review.
Workflow step: Step 6 — audit after every decision or blocked action.
Inputs: typed AuditEvent values.
Outputs: one JSON object per line.
Controls/rights: append-only file writes preserve an inspectable event trail.
"""

from __future__ import annotations

import json
from pathlib import Path

from src.models import AuditEvent


class AuditLog:
    """Write structured audit events to a JSONL file."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, event: AuditEvent) -> None:
        """Append one event without overwriting prior events."""

        with self.path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(event.model_dump(mode="json"), sort_keys=True) + "\n")
