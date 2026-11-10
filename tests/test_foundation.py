"""Smoke tests for Stage 1 foundation models and least-privilege defaults."""

from datetime import date

import config
from src.models import Action, Signal, SignalDirection, StyleWeek


def test_style_week_accepts_the_documented_shape() -> None:
    style = StyleWeek(
        style_id="S017",
        category="lounge",
        week="2026-W14",
        region="north_america",
        sales_last_4w=[410, 395, 372, 350],
        weeks_of_supply=11.2,
        return_rate=0.14,
        open_order_units=6000,
        vendor_cutoff_date=date(2026, 4, 20),
        data_as_of=date(2026, 4, 13),
        signals=[
            Signal(
                source_type="review",
                text="Seam rubs after one wash.",
                direction=SignalDirection.DOWN,
                strength=0.8,
                date=date(2026, 3, 30),
            )
        ],
        label=Action.CUT_REORDER,
    )

    assert style.style_id == "S017"
    assert style.signals[0].source_type == "review"


def test_forbidden_actions_are_denied_by_default() -> None:
    assert config.AGENT_RIGHTS["submit_vendor_po"] is False
    assert config.AGENT_RIGHTS["retire_style"] is False
    assert config.AGENT_RIGHTS["draft_order_cut"] is True
