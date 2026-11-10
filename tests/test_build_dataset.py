"""Tests for the deterministic offline dataset build."""

import json
from pathlib import Path

from src.build_dataset import build_dataset, cohen_kappa


def test_build_dataset_creates_reproducible_split_and_labels(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"

    assert build_dataset(first, seed=7) == build_dataset(second, seed=7)
    assert len(list((first / "styles").glob("*.json"))) == 100
    assert len(list((first / "signals").glob("*.json"))) == 100
    assert len((first / "labels.csv").read_text(encoding="utf-8").splitlines()) == 101

    splits = json.loads((first / "splits.json").read_text(encoding="utf-8"))
    assert len(splits["dev"]) == 60
    assert len(splits["holdout"]) == 40
    assert splits["dev"] == json.loads((second / "splits.json").read_text(encoding="utf-8"))["dev"]


def test_labels_include_broader_actions_and_kappa(tmp_path: Path) -> None:
    assert cohen_kappa(["fix", "hold", "fix"], ["fix", "fix", "fix"]) == 0.0
    output = tmp_path / "data"
    build_dataset(output, seed=7)
    labels = (output / "labels.csv").read_text(encoding="utf-8")
    assert "move" in labels
    assert "retire" in labels
