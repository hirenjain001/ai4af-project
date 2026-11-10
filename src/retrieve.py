"""Retrieve cited context from the three local RAG stores.

Purpose: provide deterministic, source-aware context to the reasoning node.
Workflow step: Step 2 — retrieve context.
Inputs: natural-language query, optional style, and store directory.
Outputs: ranked RetrievedChunk objects with source names and dates.
Controls/rights: stale market signals are excluded before ranking.
"""

from __future__ import annotations

import json
import re
from datetime import date, timedelta
from pathlib import Path

import chromadb

from src.embeddings import DeterministicEmbeddingFunction
from src.models import RetrievedChunk


def _tokens(text: str) -> set[str]:
    """Normalize query words for deterministic lexical matching."""

    return set(re.findall(r"[a-z0-9]+", text.lower()))


def _load(path: Path) -> list[RetrievedChunk]:
    """Load one JSONL store."""

    if not path.exists():
        return []
    return [
        RetrievedChunk.model_validate(json.loads(line))
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def retrieve(
    query: str,
    store: str,
    store_dir: Path = Path("data/rag"),
    *,
    style_id: str | None = None,
    as_of: date = date(2026, 4, 13),
    last_n_weeks: int = 8,
    top_k: int = 3,
) -> list[RetrievedChunk]:
    """Return the most relevant, cited chunks from one store.

    Args:
        query: Signal or planning question.
        store: One of playbook, market_signals, or past_decisions.
        store_dir: Directory containing ingested JSONL stores.
        style_id: Optional style filter for market and decision stores.
        as_of: Reference date for freshness filtering.
        last_n_weeks: Maximum age for market-signal chunks.
        top_k: Maximum number of chunks returned.

    Returns:
        Ranked chunks with valid provenance.
    """

    if store not in {"playbook", "market_signals", "past_decisions"}:
        raise ValueError(f"Unknown RAG store: {store}")
    chroma_path = store_dir / "chroma"
    if chroma_path.exists():
        collection = chromadb.PersistentClient(path=str(chroma_path)).get_collection(
            name=store,
        )
        where: dict[str, str] | None = None
        if style_id and store in {"market_signals", "past_decisions"}:
            where = {"style_id": style_id}
        result = collection.query(
            query_embeddings=DeterministicEmbeddingFunction()([query]),
            n_results=max(top_k * 3, top_k),
            where=where,
            include=["documents", "metadatas", "distances"],
        )
        documents = result.get("documents", [[]])[0]
        metadatas = result.get("metadatas", [[]])[0]
        distances = result.get("distances", [[]])[0]
        chunks = [
            RetrievedChunk(
                text=text,
                source=metadata["source"],
                date=date.fromisoformat(metadata["date"]),
                store=metadata["store"],
                style_id=metadata.get("style_id") or None,
                score=max(0.0, 1.0 - float(distance)),
            )
            for text, metadata, distance in zip(documents, metadatas, distances)
        ]
    else:
        chunks = _load(store_dir / f"{store}.jsonl")
    query_tokens = _tokens(query)
    cutoff = as_of - timedelta(weeks=last_n_weeks)
    if store == "market_signals":
        chunks = [chunk for chunk in chunks if chunk.date >= cutoff]
    if style_id and store in {"market_signals", "past_decisions"}:
        style_chunks = [chunk for chunk in chunks if chunk.style_id == style_id]
        if style_chunks:
            chunks = style_chunks
    ranked = sorted(
        chunks,
        key=lambda chunk: (
            len(query_tokens & _tokens(chunk.text)),
            chunk.date,
        ),
        reverse=True,
    )
    return ranked[:top_k]
