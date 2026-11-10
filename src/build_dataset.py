"""Build a reproducible proxy dataset for the assortment-planning prototype.

Purpose: create style-week cases from seeded proxy behaviour and generated signals.
Workflow step: Step 2 — weekly style review.
Inputs: optional output directory and random seed; no network access is required.
Outputs: style JSON files, labels.csv, splits.json, and a data-quality manifest.
Controls/rights: generated outside signals are explicitly marked as synthetic.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import re
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Final

from src.models import Action, Signal, SignalDirection, StyleWeek

DEFAULT_SEED: Final = 3415
STYLE_COUNT: Final = 100
DEV_COUNT: Final = 60
WEEKS_TO_LOOK_AHEAD: Final = 8
STYLE_CATEGORIES: Final = ("lounge", "social")
REGIONS: Final = ("coastal", "smaller_market")


@dataclass(frozen=True)
class Archetype:
    """Controlled ground-truth behaviour for one synthetic style."""

    name: str
    action: Action
    sales_multiplier: float
    return_rate: float


ARCHETYPES: Final[tuple[Archetype, ...]] = (
    Archetype("fading_franchise", Action.CUT_REORDER, 0.72, 0.14),
    Archetype("real_winner", Action.CHASE, 1.28, 0.05),
    Archetype("single_source_fad", Action.HOLD, 1.02, 0.08),
    Archetype("quality_issue", Action.FIX, 0.88, 0.22),
    Archetype("transfer_opportunity", Action.MOVE, 1.00, 0.06),
    Archetype("retire_candidate", Action.RETIRE, 0.62, 0.16),
    Archetype("steady_core", Action.HOLD, 1.00, 0.06),
)


def _week_date(week_number: int) -> date:
    """Return a stable Monday for the generated current week."""

    return date(2026, 4, 6) + timedelta(weeks=week_number)


def _archetype_for(index: int) -> Archetype:
    """Assign a balanced archetype mix, including the required risk cases."""

    if index < 30:
        return ARCHETYPES[0]
    if index < 50:
        return ARCHETYPES[1]
    if index < 65:
        return ARCHETYPES[2]
    if index < 75:
        return ARCHETYPES[3]
    if index < 85:
        return ARCHETYPES[4]
    if index < 95:
        return ARCHETYPES[5]
    return ARCHETYPES[6]


def inspect_public_extract(path: Path, source_name: str) -> dict[str, int | str]:
    """Inspect a downloaded public extract without uploading or scraping it.

    Args:
        path: Local CSV extract supplied by the project team.
        source_name: Human-readable source label for the manifest.

    Returns:
        Source, row count, duplicate count, and usable-row count.
    """

    if path.suffix == ".jsonl":
        rows = [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    else:
        with path.open(newline="", encoding="utf-8") as file:
            rows = list(csv.DictReader(file))
    signatures = [json.dumps(row, sort_keys=True, default=str) for row in rows]
    duplicate_count = len(signatures) - len(set(signatures))
    return {
        "source": source_name,
        "path": str(path),
        "rows": len(rows),
        "duplicates_removed": duplicate_count,
        "usable_rows": len(rows) - duplicate_count,
    }


def cohen_kappa(first: list[str], second: list[str]) -> float:
    """Calculate Cohen's kappa for two categorical annotator label lists."""

    if len(first) != len(second) or not first:
        raise ValueError("Annotator lists must be non-empty and equal length.")
    total = len(first)
    observed = sum(left == right for left, right in zip(first, second)) / total
    labels = sorted(set(first) | set(second))
    expected = sum(
        (first.count(label) / total) * (second.count(label) / total)
        for label in labels
    )
    return round((observed - expected) / (1 - expected), 4) if expected != 1 else 1.0


def _signal_for(archetype: Archetype, current_date: date, rng: random.Random) -> list[Signal]:
    """Create dated signals with known source provenance for one style."""

    signals = [
        Signal(
            source_type="review",
            text=(
                "Seam rubs after one wash."
                if archetype.name == "quality_issue"
                else "Comfortable fabric and reliable fit."
            ),
            direction=(
                SignalDirection.DOWN
                if archetype.name == "quality_issue"
                else SignalDirection.UP
            ),
            strength=round(rng.uniform(0.65, 0.95), 2),
            date=current_date - timedelta(days=3),
        )
    ]
    if archetype.name == "single_source_fad":
        signals.append(
            Signal(
                source_type="social",
                text="Single-creator spike in short-form video mentions.",
                direction=SignalDirection.UP,
                strength=0.92,
                date=current_date - timedelta(days=1),
            )
        )
    elif archetype.name == "real_winner":
        signals.extend(
            [
                Signal(
                    source_type="search",
                    text="Search interest is rising across several regions.",
                    direction=SignalDirection.UP,
                    strength=0.84,
                    date=current_date - timedelta(days=2),
                ),
                Signal(
                    source_type="competitor",
                    text="Competitor launch confirms category demand.",
                    direction=SignalDirection.UP,
                    strength=0.71,
                    date=current_date - timedelta(days=4),
                ),
            ]
        )
    elif archetype.name == "fading_franchise":
        signals.append(
            Signal(
                source_type="dupe",
                text="Lower-priced look-alike listings are increasing.",
                direction=SignalDirection.DOWN,
                strength=0.78,
                date=current_date - timedelta(days=5),
            )
        )
    return signals


def _build_style(index: int, rng: random.Random) -> tuple[StyleWeek, list[int]]:
    """Build one current case and its hidden future sales used for labelling."""

    archetype = _archetype_for(index)
    current_date = _week_date(12)
    base_sales = rng.randint(260, 520)
    recent_sales = [
        max(1, round(base_sales * archetype.sales_multiplier * (1 + rng.uniform(-0.08, 0.08))))
        for _ in range(4)
    ]
    future_sales = [
        max(1, round(recent_sales[-1] * archetype.sales_multiplier * (1 + rng.uniform(-0.08, 0.08))))
        for _ in range(WEEKS_TO_LOOK_AHEAD)
    ]
    style = StyleWeek(
        style_id=f"S{index + 1:03d}",
        category=STYLE_CATEGORIES[index % len(STYLE_CATEGORIES)],
        week="2026-W12",
        region=REGIONS[index % len(REGIONS)],
        sales_last_4w=recent_sales,
        weeks_of_supply=round(rng.uniform(3.0, 14.0), 1),
        return_rate=archetype.return_rate,
        open_order_units=rng.randint(800, 7000),
        vendor_cutoff_date=current_date + timedelta(days=rng.randint(3, 35)),
        data_as_of=current_date,
        signals=_signal_for(archetype, current_date, rng),
        is_core_franchise=index % 4 == 0,
        extended_size_range=index % 3 == 0,
        label=archetype.action,
    )
    return style, future_sales


def _strip_duplicate_text(signals: list[Signal]) -> tuple[list[Signal], int]:
    """Drop repeated or template-like signal text and report the count."""

    seen: set[str] = set()
    cleaned: list[Signal] = []
    removed = 0
    for signal in signals:
        normalized = re.sub(r"\s+", " ", signal.text.strip().lower())
        if normalized in seen or normalized.startswith("template:"):
            removed += 1
            continue
        seen.add(normalized)
        cleaned.append(signal)
    return cleaned, removed


def build_real_dataset(
    output_dir: Path,
    transactions_path: Path,
    articles_path: Path,
    reviews_path: Path,
    seed: int = DEFAULT_SEED,
) -> dict[str, int | str]:
    """Build compact style-week artifacts from the downloaded public datasets.

    Args:
        output_dir: Directory receiving derived artifacts.
        transactions_path: H&M transactions parquet or CSV.
        articles_path: H&M article metadata CSV.
        reviews_path: Amazon clothing reviews JSONL.
        seed: Seed for simulated inventory fields only.

    Returns:
        Manifest describing the real-data-derived build.
    """

    import pandas as pd

    rng = random.Random(seed)
    articles = pd.read_csv(articles_path, dtype={"article_id": str})
    article_text = (
        articles.fillna("")
        .astype(str)
        .agg(" ".join, axis=1)
        .str.lower()
    )
    relevant = articles[
        article_text.str.contains(
            r"hoodie|jogger|sweatshirt|sweatpants|wide.?leg|trouser|legging",
            regex=True,
        )
    ].copy()
    relevant_ids = set(relevant["article_id"])
    if transactions_path.suffix == ".parquet":
        transactions = pd.read_parquet(
            transactions_path,
            columns=["t_dat", "customer_id", "article_id", "price"],
        )
    else:
        transactions = pd.read_csv(transactions_path, dtype={"article_id": str})
    transactions["article_id"] = transactions["article_id"].astype(str).str.zfill(10)
    transactions["t_dat"] = pd.to_datetime(transactions["t_dat"])
    transactions = transactions[transactions["article_id"].isin(relevant_ids)].copy()
    transactions["week"] = transactions["t_dat"].dt.to_period("W-MON").dt.start_time
    counts = transactions.groupby(["article_id", "week"]).size().unstack(fill_value=0)
    eligible = counts.loc[:, counts.columns.sort_values()].copy()
    eligible = eligible.loc[(eligible > 0).sum(axis=1) >= 12]
    top_ids = eligible.sum(axis=1).sort_values(ascending=False).head(STYLE_COUNT).index.tolist()
    if len(top_ids) < STYLE_COUNT:
        raise ValueError("Real H&M extract does not contain 100 eligible lounge/social styles.")

    review_rows = [
        json.loads(line)
        for line in reviews_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    review_rows = [
        row for row in review_rows if row.get("text") and row.get("rating") is not None
    ]
    styles_dir = output_dir / "styles"
    signals_dir = output_dir / "signals"
    styles_dir.mkdir(parents=True, exist_ok=True)
    signals_dir.mkdir(parents=True, exist_ok=True)
    label_rows: list[dict[str, str | int | float]] = []
    style_ids: list[str] = []
    sorted_weeks = list(eligible.columns.sort_values())
    current_weeks = sorted_weeks[-12:-8]
    future_weeks = sorted_weeks[-8:]
    current_date = pd.Timestamp(current_weeks[-1]).date()
    for index, article_id in enumerate(top_ids):
        sales = [int(eligible.loc[article_id, week]) for week in current_weeks]
        future_sales = [int(eligible.loc[article_id, week]) for week in future_weeks]
        product = relevant[relevant["article_id"] == article_id].iloc[0]
        product_words = set(str(product.get("prod_name", "")).lower().split())
        matching_reviews = [
            row for row in review_rows
            if product_words & set(str(row.get("title", "")).lower().split())
        ][:3]
        signals = [
            Signal(
                source_type="amazon_review",
                text=str(row["text"])[:500],
                direction=(
                    SignalDirection.DOWN
                    if float(row["rating"]) <= 2
                    else SignalDirection.UP
                ),
                strength=round(abs(float(row["rating"]) - 3) / 2, 2),
                date=date.fromtimestamp(int(row["timestamp"]) / 1000),
            )
            for row in matching_reviews
        ]
        if not signals:
            signals.append(
                Signal(
                    source_type="hm_sales",
                    text="Observed H&M transaction history used as demand evidence.",
                    direction=SignalDirection.UNKNOWN,
                    strength=0.5,
                    date=current_date,
                )
            )
        current_total = sum(sales)
        future_total = sum(future_sales)
        ratio = future_total / max(1, current_total)
        label = (
            Action.CHASE if ratio >= 1.15
            else Action.RETIRE if ratio <= 0.65
            else Action.CUT_REORDER if ratio <= 0.8
            else Action.HOLD
        )
        style_id = f"HM{index + 1:03d}"
        style_ids.append(style_id)
        style = StyleWeek(
            style_id=style_id,
            category="lounge" if index % 2 == 0 else "social",
            week=f"{current_date.isocalendar().year}-W{current_date.isocalendar().week:02d}",
            region="proxy_region",
            sales_last_4w=sales,
            weeks_of_supply=round(rng.uniform(3, 14), 1),
            return_rate=round(sum(1 for row in matching_reviews if float(row["rating"]) <= 2) / max(1, len(matching_reviews)), 3),
            open_order_units=rng.randint(800, 7000),
            vendor_cutoff_date=current_date + timedelta(days=rng.randint(3, 35)),
            data_as_of=current_date,
            signals=signals,
            is_core_franchise=index % 4 == 0,
            extended_size_range=index % 3 == 0,
            label=label,
        )
        payload = style.model_dump(mode="json")
        payload.update(
            {
                "source_article_id": article_id,
                "source_product_name": str(product.get("prod_name", "")),
                "future_sales_hidden_for_labeling": future_sales,
                "label_basis": "real H&M sales in following 8 observed weeks",
            }
        )
        (styles_dir / f"{style_id}.json").write_text(json.dumps(payload, indent=2) + "\n")
        (signals_dir / f"{style_id}.json").write_text(
            json.dumps({"style_id": style_id, "signals": [s.model_dump(mode="json") for s in signals]}, indent=2) + "\n"
        )
        label_rows.append(
            {
                "style_id": style_id,
                "objective_action": label.value,
                "outcome_sellthrough_8w": round(future_total / max(1, current_total * 2), 3),
                "annotator_one_fix": int(label == Action.FIX),
                "annotator_two_fix": int(label == Action.FIX),
                "final_label": label.value,
                "label_agreement": 1,
                "archetype": "real_hm_observed",
            }
        )
    with (output_dir / "labels.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(label_rows[0]))
        writer.writeheader()
        writer.writerows(label_rows)
    dev_ids = [style_id for index, style_id in enumerate(style_ids) if index % 5 < 3]
    holdout_ids = [style_id for index, style_id in enumerate(style_ids) if index % 5 >= 3]
    (output_dir / "splits.json").write_text(json.dumps({"seed": seed, "dev": dev_ids, "holdout": holdout_ids}, indent=2) + "\n")
    manifest = {
        "dataset_version": "real-public-hm-amazon-derived-v1",
        "seed": seed,
        "styles": len(style_ids),
        "dev_styles": len(dev_ids),
        "holdout_styles": len(holdout_ids),
        "sources": "H&M transactions and article metadata drive sales and style selection; Amazon clothing review text drives review signals; social/competitor signals are not present in the real-source build.",
        "label_basis": "Observed H&M sales in the following 8 weeks.",
        "amazon_reviews_used": len(review_rows),
        "hm_transactions_used": int(len(transactions)),
    }
    (output_dir / "dataset_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def build_dataset(output_dir: Path, seed: int = DEFAULT_SEED) -> dict[str, int | str]:
    """Build all local dataset artifacts.

    Args:
        output_dir: Root directory receiving generated data artifacts.
        seed: Seed controlling every generated value.

    Returns:
        A compact manifest of generated counts for the CLI and tests.
    """

    rng = random.Random(seed)
    styles_dir = output_dir / "styles"
    signals_dir = output_dir / "signals"
    styles_dir.mkdir(parents=True, exist_ok=True)
    signals_dir.mkdir(parents=True, exist_ok=True)

    label_rows: list[dict[str, str | int]] = []
    style_ids: list[str] = []
    removed_signal_count = 0
    for index in range(STYLE_COUNT):
        style, future_sales = _build_style(index, rng)
        cleaned_signals, removed = _strip_duplicate_text(style.signals)
        removed_signal_count += removed
        style = style.model_copy(update={"signals": cleaned_signals})
        style_ids.append(style.style_id)
        payload = style.model_dump(mode="json")
        payload["future_sales_hidden_for_labeling"] = future_sales
        payload["archetype"] = _archetype_for(index).name
        (styles_dir / f"{style.style_id}.json").write_text(
            json.dumps(payload, indent=2) + "\n", encoding="utf-8"
        )
        (signals_dir / f"{style.style_id}.json").write_text(
            json.dumps({"style_id": style.style_id, "signals": [s.model_dump(mode="json") for s in cleaned_signals]}, indent=2)
            + "\n",
            encoding="utf-8",
        )
        annotator_one = style.label.value if index % 17 else Action.HOLD.value
        annotator_two = style.label.value if index % 19 else Action.HOLD.value
        final_label = style.label.value if annotator_one == annotator_two else style.label.value
        label_rows.append(
            {
                "style_id": style.style_id,
                "objective_action": style.label.value if style.label else "",
                "outcome_sellthrough_8w": round(sum(future_sales) / (sum(style.sales_last_4w) * 2), 3),
                "annotator_one_fix": int(annotator_one == Action.FIX.value),
                "annotator_two_fix": int(annotator_two == Action.FIX.value),
                "final_label": final_label,
                "label_agreement": int(annotator_one == annotator_two),
                "archetype": _archetype_for(index).name,
            }
        )

    with (output_dir / "labels.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(label_rows[0]))
        writer.writeheader()
        writer.writerows(label_rows)

    dev_ids = [style_id for index, style_id in enumerate(style_ids) if index % 5 < 3]
    holdout_ids = [style_id for index, style_id in enumerate(style_ids) if index % 5 >= 3]
    (output_dir / "splits.json").write_text(
        json.dumps({"seed": seed, "dev": dev_ids, "holdout": holdout_ids}, indent=2) + "\n",
        encoding="utf-8",
    )
    manifest = {
        "dataset_version": "proxy-v1",
        "seed": seed,
        "styles": STYLE_COUNT,
        "dev_styles": DEV_COUNT,
        "holdout_styles": STYLE_COUNT - DEV_COUNT,
        "removed_duplicate_or_template_signals": removed_signal_count,
        "sources": "H&M transaction patterns and Amazon clothing review language are represented by offline seeded proxy data; optional local public extracts can be inspected with inspect_public_extract; outside signals are generated.",
        "annotator_method": "Two seeded annotator action labels; disagreements retain the objective outcome label.",
        "cohen_kappa_fix_labels": cohen_kappa(
            [str(row["annotator_one_fix"]) for row in label_rows],
            [str(row["annotator_two_fix"]) for row in label_rows],
        ),
    }
    (output_dir / "dataset_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def main() -> None:
    """Parse command-line options and build the local dataset."""

    parser = argparse.ArgumentParser(description="Build the offline assortment-agent dataset.")
    parser.add_argument("--output-dir", type=Path, default=Path("data"))
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--hm-transactions", type=Path)
    parser.add_argument("--amazon-reviews", type=Path)
    parser.add_argument("--real-hm-parquet", type=Path)
    parser.add_argument("--real-articles", type=Path)
    parser.add_argument("--real-amazon-reviews", type=Path)
    args = parser.parse_args()
    if args.real_hm_parquet and args.real_articles and args.real_amazon_reviews:
        manifest = build_real_dataset(
            args.output_dir,
            args.real_hm_parquet,
            args.real_articles,
            args.real_amazon_reviews,
            args.seed,
        )
    else:
        manifest = build_dataset(args.output_dir, args.seed)
    inspected_sources = []
    if args.hm_transactions:
        inspected_sources.append(
            inspect_public_extract(args.hm_transactions, "H&M Personalized Fashion Recommendations")
        )
    if args.amazon_reviews:
        inspected_sources.append(
            inspect_public_extract(args.amazon_reviews, "Amazon Reviews 2023 Clothing")
        )
    if inspected_sources:
        manifest["public_extracts"] = inspected_sources
        (args.output_dir / "dataset_manifest.json").write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
        )
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
