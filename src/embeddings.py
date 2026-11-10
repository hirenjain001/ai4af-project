"""Offline deterministic embeddings for the local Chroma stores.

Purpose: provide a reproducible embedding function without model downloads.
Workflow step: Step 2 — retrieve context before signal reasoning.
Inputs: document or query text.
Outputs: fixed-size normalized vectors accepted by Chroma.
Controls/rights: no external text service or personal data leaves the process.
"""

from __future__ import annotations

import hashlib
import math


class DeterministicEmbeddingFunction:
    """Create stable hash-based vectors for offline retrieval."""

    dimension = 64

    def name(self) -> str:
        """Return Chroma's stable embedding-function identifier."""

        return "deterministic-hash-v1"

    def is_legacy(self) -> bool:
        """Declare the current Chroma embedding-function interface."""

        return False

    def __call__(self, input: list[str]) -> list[list[float]]:
        """Embed each text deterministically for local semantic-style matching."""

        return [self._embed(text) for text in input]

    @classmethod
    def _embed(cls, text: str) -> list[float]:
        """Map token hashes into a normalized fixed-size vector."""

        vector = [0.0] * cls.dimension
        for token in text.lower().split():
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:2], "big") % cls.dimension
            vector[index] += 1.0 if digest[2] % 2 else -1.0
        magnitude = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [round(value / magnitude, 8) for value in vector]
