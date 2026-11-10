"""Deterministic merchandising metrics for the assortment-planning prototype.

Purpose: calculate transparent metrics used by baseline and agent nodes.
Workflow step: Step 2 — weekly style review.
Inputs: validated StyleWeek cases.
Outputs: sell-through, trend, and inventory-risk values.
Controls/rights: reads internal-style fields only; no external action is performed.
"""

from __future__ import annotations

from src.models import StyleWeek


def sell_through(style: StyleWeek) -> float:
    """Estimate four-week sell-through from sales and open orders.

    Args:
        style: Style-week data containing recent sales and open orders.

    Returns:
        A bounded proxy sell-through ratio for transparent comparisons.
    """

    denominator = sum(style.sales_last_4w) + style.open_order_units
    return round(sum(style.sales_last_4w) / denominator, 4) if denominator else 0.0


def sales_trend(style: StyleWeek) -> float:
    """Calculate relative movement from the first to latest weekly sales value."""

    first, latest = style.sales_last_4w[0], style.sales_last_4w[-1]
    return round((latest - first) / first, 4) if first else 0.0


def inventory_risk(style: StyleWeek) -> str:
    """Classify weeks of supply into a simple planning risk band."""

    if style.weeks_of_supply >= 10:
        return "excess"
    if style.weeks_of_supply <= 5:
        return "tight"
    return "balanced"
