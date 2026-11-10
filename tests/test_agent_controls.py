"""Tests for control gates and graph routing."""

from datetime import date, timedelta
from pathlib import Path

import config
from src.agent import run
from src.build_dataset import build_dataset
from src.controls import cutoff_watchdog, freshness_guard, grounding_check, markdown_guard, strip_pii
from src.ingest import ingest
from src.models import Action, Citation, Recommendation, RetrievedChunk, StyleWeek


def test_controls_cover_stale_cutoff_markdown_grounding_and_pii() -> None:
    style = StyleWeek(
        style_id="S001",
        category="lounge",
        week="2026-W12",
        region="coastal",
        sales_last_4w=[100, 100, 100, 100],
        weeks_of_supply=10,
        return_rate=0.05,
        open_order_units=100,
        vendor_cutoff_date=date(2026, 4, 15),
        data_as_of=date(2026, 4, 1),
    )
    assert freshness_guard(style, date(2026, 4, 13)).route == "hold_and_flag_data"
    assert cutoff_watchdog(style, date(2026, 4, 13)).route == "escalate_to_planner"
    assert markdown_guard(style, 25).route == "escalate_to_planner"
    assert strip_pii("email me at guest@example.com or @guest") == "email me at [REDACTED_EMAIL] or [REDACTED_HANDLE]"
    recommendation = Recommendation(
        action=Action.CHASE,
        confidence=0.9,
        rationale="A recommendation",
        citations=[Citation(source="one", date=date(2026, 4, 1))],
    )
    chunks = [RetrievedChunk(text="one", source="one", date=date(2026, 4, 1), store="market_signals")]
    assert grounding_check(recommendation, chunks).route == "hold_and_watch"


def test_graph_retrieves_three_stores_and_writes_audit(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    build_dataset(data_dir, seed=5)
    store_dir = tmp_path / "rag"
    ingest(data_dir, Path("kb"), store_dir)
    style = StyleWeek.model_validate(__import__("json").loads((data_dir / "styles" / "S001.json").read_text()) | {"future_sales_hidden_for_labeling": None, "archetype": None})
    result = run(style, store_dir, audit_path=tmp_path / "audit.jsonl")
    assert result.route in {"draft_for_approval", "escalate_to_planner", "hold_and_watch"}
    assert len(result.events) >= 5
    assert (tmp_path / "audit.jsonl").exists()


def test_runtime_kill_switch_override_routes_to_manual_queue(tmp_path: Path) -> None:
    style = StyleWeek(
        style_id="S001",
        category="lounge",
        week="2026-W12",
        region="coastal",
        sales_last_4w=[100, 100, 100, 100],
        weeks_of_supply=6,
        return_rate=0.05,
        open_order_units=100,
        vendor_cutoff_date=date(2026, 4, 30),
        data_as_of=date(2026, 4, 13),
    )
    result = run(style, tmp_path / "missing-rag", kill_switch_override=True)
    assert result.route == "manual_queue"
    assert result.events[0].node == "check_kill_switch"
