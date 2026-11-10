"""Tests for ingestion, citation metadata, and stale-signal filtering."""

from datetime import date, timedelta
from pathlib import Path

from src.build_dataset import build_dataset
from src.ingest import ingest
from src.retrieve import retrieve


def test_three_stores_return_cited_chunks(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    build_dataset(data_dir, seed=3)
    kb_dir = Path("kb")
    store_dir = tmp_path / "rag"
    counts = ingest(data_dir, kb_dir, store_dir)

    assert counts["playbook"] > 0
    assert counts["market_signals"] > 0
    assert counts["past_decisions"] == 60
    results = retrieve("markdown policy", "playbook", store_dir)
    assert results
    assert results[0].source == "kb/playbook.md"
    assert results[0].date == date(2026, 4, 1)


def test_market_retrieval_filters_stale_chunks(tmp_path: Path) -> None:
    store_dir = tmp_path / "rag"
    store_dir.mkdir()
    old_date = date(2026, 4, 13) - timedelta(weeks=9)
    (store_dir / "market_signals.jsonl").write_text(
        '{"text":"old social demand spike","source":"old.json","date":"'
        + old_date.isoformat()
        + '","store":"market_signals","style_id":"S001","score":1.0}\n',
        encoding="utf-8",
    )
    assert retrieve("social demand spike", "market_signals", store_dir) == []
