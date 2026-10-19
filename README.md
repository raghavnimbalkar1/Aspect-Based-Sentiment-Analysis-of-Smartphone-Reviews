# Smartphone Review Analysis

A local workspace for aspect-based sentiment analysis of smartphone reviews. The project covers data preparation, annotation, baseline and transformer experiments, and a dashboard for investigating the evidence behind feature-level sentiment.

The implementation follows the approved [research proposal](RESEARCH_PLAN.md). See the [delivery phases](docs/DELIVERY.md) for progress and acceptance criteria.

## Current increment

- A React dashboard with aspect charts, single-review analysis, linked review filters, phone comparison, and CSV/JSON exports.
- A local FastAPI service with SQLite migrations, validated imports, persistent results, and resumable batch analysis.
- A verified historical corpus of 4,346 reviews across 12 explicitly selected smartphone models/listings.
- A rule baseline using explicit aspect cues and VADER, with source sentences attached to predictions.
- Blind annotation exports, duplicate-aware review partitions, exact tuple metrics, and a TF-IDF training command.

**The active model is a rule baseline.** Human annotation and supervised model experiments are the next phase. No transformer performance or held-out accuracy is claimed.

## Run locally

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) and Node.js 24 or later. The project uses Python 3.12 through uv. Run these commands from the repository root:

```sh
make setup
make data
make seed
make build
make run
```

Open [http://localhost:8000](http://localhost:8000). After setup, `make run` uses the saved database and built dashboard without internet. You can also start with `bash scripts/start.sh`.

`make data` downloads the fixed public Kaggle source version, verifies CSV checksums, applies the explicit smartphone selection, filters language, removes repeated listing/text rows, and writes a bounded corpus. `make seed` imports it idempotently and runs the baseline. Neither command writes raw reviews or databases into Git.

The source spans older devices and includes explicitly marked renewed listings. This workspace describes those historical reviews; it does not rank current phones. See the [data audit](docs/data/README.md).

## Work with your own reviews

Choose **Import reviews**, upload a UTF-8 CSV, and map its text column. Product, brand, date, and rating columns are optional. The importer reports invalid rows and duplicates. Dates accept ISO format, English month names, or `MM/DD/YYYY`; individual review text is limited to 30,000 characters. The upload limit is 16 MB and 10,000 rows.

Choose **Run analysis** to process an imported dataset. Completed records persist as the job advances. After an interruption, retry processes only unfinished records. Use one API process/worker per database.

The source import filters detected non-English reviews. Custom uploads retain them for visibility, while analysis marks unsupported languages instead of creating aspect results. Short text may have uncertain language identification and is processed provisionally. Product relevance in custom uploads is supplied by the user.

The explorer, overview, and exports use the same review filters. The comparison screen is a separate full-corpus view for the selected products. Main charts count each review/category once. Net sentiment is `(positive − negative) / all present-state mentions × 100`; neutral and mixed mentions stay in the denominator. Low-support comparisons are identified.

## Annotation and experiments

```sh
make pilot
uv run absa annotation-tasks data/processed/reviews.jsonl --output data/annotations/full.csv --sentences 1200 --full
```

Follow the [annotation guide](docs/ANNOTATION.md), preserve the sidecar manifests, and independently check the labels before training:

```sh
uv run absa train-tfidf data/annotations/reconciled.csv --manifest data/annotations/full.manifest.json --output artifacts/experiments/tfidf-001
```

This produces validation comparisons for rules, TF-IDF, and always-absent predictions. The evaluation page reads the resulting metrics. Test evaluation requires the explicit `--final-test` option and belongs after model selection. Existing task and experiment output paths are protected against overwrites.

## Development and checks

```sh
make check
```

For separate development servers, run `make dev-api` and `make dev-ui` in two terminals, then open [http://localhost:5173](http://localhost:5173). The frontend proxies API calls to port 8000. Production-style local serving uses the built frontend through the single backend process.

The SQLite database defaults to `data/workspace.sqlite3`. Override it with `ABSA_DATABASE`. Numbered migrations under `src/smartphone_absa/migrations` apply automatically and are checked for changes after application. Back up a valuable local database before upgrading it.

Model and taxonomy IDs participate in persistence keys. A behaviour-changing baseline update must receive a new model ID before processing existing data. Model files, experiment outputs, annotation copies, and database files stay local.

## Repository layout

| Path | Purpose |
| --- | --- |
| `src/smartphone_absa` | API, storage, data preparation, annotation, models, and metrics |
| `frontend` | React/TypeScript dashboard |
| `config/products.json` | Reviewed smartphone listing selection |
| `docs/data` | Source checksums and aggregate preparation evidence |
| `docs/ANNOTATION.md` | Annotation and evaluation instructions |
| `tests` | Model behaviour, leakage, persistence, import, and API checks |
| `data` / `artifacts` | Local generated data, databases, labels, and experiments; ignored by Git |

## Delivery

1. Data audit, annotation format, grouped splits, and reproducible baseline.
2. Local API, persistent analysis jobs, and dashboard.
3. Supervised model comparison and local transformer inference.
4. Final evaluation, verification, and submission packaging.

Review-level ratings are metadata. They are never substituted for aspect sentiment labels. Real model measurements will be published only after evaluation on independently checked annotations.

## Development workflow

Use focused feature branches and pull requests. Raw datasets, local databases, trained checkpoints, credentials, and generated exports stay out of Git. See [contribution guidance](CONTRIBUTING.md).
