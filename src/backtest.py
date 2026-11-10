"""Deterministic financial backtest for baseline and future agent policies.

Purpose: estimate markdown cost and full-price sell-through under a decision.
Workflow step: Step 6 — review action and financial effect.
Inputs: StyleWeek data and a proposed Action.
Outputs: a comparable BacktestResult.
Controls/rights: simulation only; it never schedules a markdown or changes price.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.models import Action, StyleWeek


@dataclass(frozen=True)
class BacktestResult:
    """Simulated financial outcome for one style-week."""

    markdown_dollars: float
    full_price_units: int
    markdown_rate: float


def simulate(style: StyleWeek, action: Action, unit_price: float = 100.0) -> BacktestResult:
    """Simulate markdown exposure using a fixed policy.

    Args:
        style: Style-week data.
        action: Proposed action to evaluate.
        unit_price: Assumed unit value for the comparison.

    Returns:
        Simulated markdown dollars, full-price units, and markdown rate.
    """

    units = sum(style.sales_last_4w)
    if action in {Action.MARKDOWN, Action.CUT_REORDER}:
        markdown_rate = 0.20 if not style.is_core_franchise else 0.0
    else:
        markdown_rate = 0.05 if style.weeks_of_supply >= 10 else 0.0
    markdown_dollars = round(units * unit_price * markdown_rate, 2)
    return BacktestResult(
        markdown_dollars=markdown_dollars,
        full_price_units=round(units * (1 - markdown_rate)),
        markdown_rate=markdown_rate,
    )
