"""Tests for metrics, baseline, backtest, and audit logging."""

from datetime import date
import json

from src.audit import AuditLog
from src.backtest import simulate
from src.baseline import plan
from src.metrics import inventory_risk, sales_trend, sell_through
from src.models import Action, AuditEvent, StyleWeek


def make_style(**overrides: object) -> StyleWeek:
    values: dict[str, object] = {
        "style_id": "S001",
        "category": "lounge",
        "week": "2026-W12",
        "region": "coastal",
        "sales_last_4w": [100, 110, 125, 140],
        "weeks_of_supply": 4.0,
        "return_rate": 0.05,
        "open_order_units": 200,
        "vendor_cutoff_date": date(2026, 4, 20),
        "data_as_of": date(2026, 4, 13),
    }
    values.update(overrides)
    return StyleWeek(**values)


def test_metrics_and_baseline_are_transparent() -> None:
    style = make_style()
    assert sell_through(style) == 0.7037
    assert sales_trend(style) == 0.4
    assert inventory_risk(style) == "tight"
    assert plan(style).action == Action.CHASE


def test_quality_risk_wins_over_demand_signal() -> None:
    style = make_style(return_rate=0.2)
    assert plan(style).action == Action.FIX


def test_backtest_and_audit_are_deterministic(tmp_path) -> None:
    style = make_style(is_core_franchise=False, weeks_of_supply=12)
    result = simulate(style, Action.MARKDOWN)
    assert result.markdown_rate == 0.2
    assert result.markdown_dollars == 9500.0

    path = tmp_path / "audit.jsonl"
    log = AuditLog(path)
    log.append(
        AuditEvent(
            timestamp="2026-04-13T00:00:00Z",
            style_id=style.style_id,
            node="baseline",
            action="markdown",
            output="excess inventory",
        )
    )
    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["style_id"] == "S001"
