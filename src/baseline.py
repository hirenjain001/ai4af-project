"""Rule-based planner used as the no-LLM comparison baseline.

Purpose: represent a cautious internal-data-only planning process.
Workflow step: Step 2 — weekly style review.
Inputs: StyleWeek metrics.
Outputs: a proposed Action and reason.
Controls/rights: proposes only; execution remains subject to later action guards.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.metrics import inventory_risk, sales_trend
from src.models import Action, StyleWeek


@dataclass(frozen=True)
class BaselineDecision:
    """Transparent baseline result for one style-week."""

    action: Action
    reason: str


def plan(style: StyleWeek) -> BaselineDecision:
    """Choose an action using only internal sales, inventory, and returns.

    Args:
        style: Style-week metrics available to a planner today.

    Returns:
        A deterministic proposed action and business explanation.
    """

    if style.return_rate >= 0.18:
        return BaselineDecision(Action.FIX, "Return rate is above the quality-risk threshold.")
    if sales_trend(style) >= 0.08 and inventory_risk(style) == "tight":
        return BaselineDecision(Action.CHASE, "Sales are rising while weeks of supply are tight.")
    if inventory_risk(style) == "excess":
        return BaselineDecision(Action.MARKDOWN, "Weeks of supply are above the excess threshold.")
    if sales_trend(style) <= -0.12:
        return BaselineDecision(Action.CUT_REORDER, "Recent sales are declining.")
    return BaselineDecision(Action.HOLD, "Internal signals do not justify a stronger action.")
