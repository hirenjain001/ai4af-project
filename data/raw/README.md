# Raw data

The repository includes bounded real public samples under
`data/raw/public_samples/`:

- `hm_articles.csv` — H&M article metadata.
- `hm_transactions_sample.csv` — a bounded H&M transaction slice.
- `hm_transactions_lounge_social_sample.csv` — the slice filtered to relevant
  lounge/social product terms.
- `amazon_clothing_reviews_sample.jsonl` — a bounded Amazon Reviews 2023
  clothing-category slice.

`SOURCE_MANIFEST.json` records source URLs and sample counts. The complete
upstream files are multi-gigabyte, so they are intentionally not copied into
this repository. `build_dataset.py --real-hm-parquet ... --real-articles ...
--real-amazon-reviews ...` builds the current real-derived style-week artifacts
from the full H&M parquet plus the bounded Amazon review sample. The default
command remains the seeded proxy mode for fast deterministic tests.
The source mapping is:

- H&M Personalized Fashion Recommendations transactions: real retail behavior.
- Amazon Reviews 2023 clothing reviews: real review language.
- Social, competitor, and dupe signals: fixed generated templates with known
  ground truth; they are not scraped from live platforms.

No proprietary lululemon data or live social feeds belong in this directory.
`data/dataset_manifest.json` records the version, seed, filters, and cleaning
counts produced by `python -m src.build_dataset`.
