"""Tests for the hold-out evaluation output."""

import json
from pathlib import Path

from evaluate import evaluate


def test_evaluation_writes_required_comparison_fields(tmp_path: Path) -> None:
    result = evaluate(tmp_path / "data", tmp_path / "results.json")
    assert result["holdout_styles"] == 40
    assert set(result["policies"]) == {"baseline", "agent_without_rag", "agent_with_rag"}
    assert 0 <= result["grounding_rate"] <= 1
    assert result["prompt_injection_tests_passed"] == 1
    assert "early_warning_lead_time_weeks_proxy" in result
    assert "full_price_sell_through" in result["policies"]["agent_with_rag"]
    assert result["planner_minutes_saved"] == 8
    saved = json.loads((tmp_path / "results.json").read_text(encoding="utf-8"))
    assert saved["policies"]["agent_with_rag"]["accuracy_ci_95"]
