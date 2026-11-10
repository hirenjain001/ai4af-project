"""Ingest the three local knowledge stores used by retrieval.

Purpose: build playbook, market-signal, and past-decision stores with provenance.
Workflow step: Step 2 — retrieve context before signal reasoning.
Inputs: kb/playbook.md and generated data artifacts.
Outputs: JSONL store files under a local store directory.
Controls/rights: every chunk carries a source and date for grounding checks.
"""

from __future__ import annotations

import json
import csv
from datetime import date
from pathlib import Path
from typing import Final

import chromadb
from chromadb.errors import NotFoundError

from src.embeddings import DeterministicEmbeddingFunction
from src.models import RetrievedChunk

STORE_NAMES: Final = ("playbook", "market_signals", "past_decisions")


def _write_store(path: Path, chunks: list[RetrievedChunk]) -> None:
    """Write one store as newline-delimited JSON."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(chunk.model_dump(mode="json")) + "\n" for chunk in chunks),
        encoding="utf-8",
    )


def _playbook_chunks(kb_dir: Path) -> list[RetrievedChunk]:
    """Split the local playbook into section-level dated chunks."""

    text = (kb_dir / "playbook.md").read_text(encoding="utf-8")
    chunks: list[RetrievedChunk] = []
    for line in text.splitlines():
        if line.startswith("## "):
            continue
        if line.strip() and not line.startswith("# "):
            chunks.append(
                RetrievedChunk(
                    text=line.strip(),
                    source="kb/playbook.md",
                    date=date(2026, 4, 1),
                    store="playbook",
                    score=1.0,
                )
            )
    return chunks


def _market_chunks(data_dir: Path) -> list[RetrievedChunk]:
    """Convert generated dated signals into market-signal chunks."""

    chunks: list[RetrievedChunk] = []
    for path in sorted((data_dir / "styles").glob("S*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        for signal in payload["signals"]:
            chunks.append(
                RetrievedChunk(
                    text=signal["text"],
                    source=f"signals/{path.name}",
                    date=date.fromisoformat(signal["date"]),
                    store="market_signals",
                    style_id=payload["style_id"],
                    score=1.0,
                )
            )
    return chunks


def _decision_chunks(data_dir: Path) -> list[RetrievedChunk]:
    """Convert development labels into past-decision examples."""

    splits = json.loads((data_dir / "splits.json").read_text(encoding="utf-8"))
    with (data_dir / "labels.csv").open(newline="", encoding="utf-8") as file:
        labels = {row["style_id"]: row for row in csv.DictReader(file)}
    return [
        RetrievedChunk(
            text=f"Past decision: {labels[style_id]['final_label']}; outcome action: {labels[style_id]['objective_action']}.",
            source="data/labels.csv",
            date=date(2026, 4, 13),
            store="past_decisions",
            style_id=style_id,
            score=1.0,
        )
        for style_id in splits["dev"]
    ]


def ingest(data_dir: Path = Path("data"), kb_dir: Path = Path("kb"), store_dir: Path = Path("data/rag")) -> dict[str, int]:
    """Build JSONL caches and three persistent Chroma collections."""

    stores = {
        "playbook": _playbook_chunks(kb_dir),
        "market_signals": _market_chunks(data_dir),
        "past_decisions": _decision_chunks(data_dir),
    }
    for name, chunks in stores.items():
        _write_store(store_dir / f"{name}.jsonl", chunks)
    chroma = chromadb.PersistentClient(path=str(store_dir / "chroma"))
    embedding_function = DeterministicEmbeddingFunction()
    for name, chunks in stores.items():
        try:
            chroma.delete_collection(name)
        except (ValueError, NotFoundError):
            pass
        collection = chroma.create_collection(
            name=name,
            embedding_function=embedding_function,
            metadata={"hnsw:space": "cosine"},
        )
        if collection.count():
            collection.delete(where={})
        collection.add(
            ids=[f"{name}-{index}" for index in range(len(chunks))],
            documents=[chunk.text for chunk in chunks],
            metadatas=[
                {
                    "source": chunk.source,
                    "date": chunk.date.isoformat(),
                    "store": chunk.store,
                    "style_id": chunk.style_id or "",
                }
                for chunk in chunks
            ],
        )
    return {name: len(chunks) for name, chunks in stores.items()}


if __name__ == "__main__":
    print(json.dumps(ingest(), indent=2))
