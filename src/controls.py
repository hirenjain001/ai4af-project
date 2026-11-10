"""Safety and rights controls for the assortment-planning agent.

Purpose: enforce freshness, contingency, grounding, PII, markdown, and rights rules.
Workflow step: Step 6 — controlled recommendation and escalation.
Inputs: StyleWeek cases, recommendations, retrieved chunks, and config thresholds.
Outputs: explicit control results or PermissionError for forbidden actions.
Controls/rights: this module is the enforcement boundary for every proposed tool call.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from functools import wraps
from pathlib import Path
from typing import Callable, TypeVar

import config
from src.audit import AuditLog
from src.models import AuditEvent
from src.models import Action, Recommendation, RetrievedChunk, StyleWeek

F = TypeVar("F", bound=Callable[..., object])


@dataclass(frozen=True)
class ControlResult:
    """A control outcome with a route and human-readable reason."""

    allowed: bool
    route: str
    reason: str


def freshness_guard(style: StyleWeek, as_of: date) -> ControlResult:
    """Hold stale internal data before any recommendation is acted on."""

    age = (as_of - style.data_as_of).days
    if age > config.MAX_DATA_AGE_DAYS:
        return ControlResult(False, "hold_and_flag_data", f"Internal data is {age} days old.")
    return ControlResult(True, "continue", "Internal data is fresh.")


def cutoff_watchdog(style: StyleWeek, as_of: date, decided: bool = False) -> ControlResult:
    """Escalate undecided styles whose vendor cutoff is close."""

    days_left = (style.vendor_cutoff_date - as_of).days
    if not decided and days_left <= config.CUTOFF_ESCALATE_DAYS:
        return ControlResult(False, "escalate_to_planner", f"Vendor cutoff is in {days_left} days.")
    return ControlResult(True, "continue", "Vendor cutoff does not require escalation.")


def strip_pii(text: str) -> str:
    """Remove emails and social handles before prompts or logs."""

    without_email = re.sub(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b", "[REDACTED_EMAIL]", text)
    return re.sub(r"(?<!\w)@[A-Za-z0-9_]+", "[REDACTED_HANDLE]", without_email)


def grounding_check(
    recommendation: Recommendation,
    chunks: list[RetrievedChunk],
) -> ControlResult:
    """Require citations and two independent source types for chases."""

    cited_sources = {citation.source for citation in recommendation.citations}
    available_sources = {chunk.source for chunk in chunks}
    if not cited_sources or not cited_sources.issubset(available_sources):
        return ControlResult(False, "escalate_to_planner", "Recommendation contains an uncited source.")
    cited_store_types = {
        chunk.store for chunk in chunks if chunk.source in cited_sources
    }
    if recommendation.action == Action.CHASE and len(cited_store_types) < 2:
        return ControlResult(False, "hold_and_watch", "A chase needs two independent cited sources.")
    return ControlResult(True, "continue", "Recommendation is grounded.")


def markdown_guard(style: StyleWeek, discount_percent: int) -> ControlResult:
    """Block over-policy markdowns and markdowns on core styles."""

    if discount_percent > 20:
        return ControlResult(False, "escalate_to_planner", "Markdown exceeds the 20% policy.")
    if style.is_core_franchise:
        return ControlResult(False, "escalate_to_planner", "Core styles require planner approval.")
    return ControlResult(True, "continue", "Markdown is within policy.")


def guarded(action: str) -> Callable[[F], F]:
    """Decorate every tool call with the least-privilege rights table."""

    def decorator(function: F) -> F:
        @wraps(function)
        def inner(*args: object, **kwargs: object) -> object:
            if not config.AGENT_RIGHTS.get(action, False):
                AuditLog(Path("data/audit.jsonl")).append(
                    AuditEvent(
                        timestamp=date.today().isoformat(),
                        style_id=str(kwargs.get("style_id", "unknown")),
                        node="action_guard",
                        action=f"blocked:{action}",
                        output=f"Blocked forbidden action {action}.",
                    )
                )
                raise PermissionError(f"Agent may not {action}")
            return function(*args, **kwargs)

        return inner  # type: ignore[return-value]

    return decorator
