# What the application does

This is a local research application for finding opinions about individual phone features. It is not an overall star-rating predictor. For example, “The camera is excellent but the battery is terrible” should produce a positive camera result and a negative battery result, each linked to the original sentence.

## Features

1. **Review intelligence:** counts positive, negative, neutral and mixed opinions across ten aspects: battery, charging, camera, display, performance/thermals, software, build/design, audio, connectivity and value. Clicking an aspect opens the relevant reviews.
2. **Single-review analysis:** accepts English text, shows detected aspects and supporting sentences, and can compare the selected neural/classical model with Rules + VADER on the same input. Timings are visible; they are not accuracy scores.
3. **Review explorer:** filters by phone, aspect, sentiment and literal text search. Expanding a review shows its evidence. The overview and exports use the same review selection.
4. **Phone comparison:** compares two or three listings, with mention counts, review dates and warnings for small samples. The net score is `(positive − negative) / all mentions × 100`. Historical or renewed listings are identified in the source selection.
5. **CSV import and export:** checks uploaded columns, reports invalid rows and duplicates, saves accepted reviews, and exports predictions as CSV or JSON. It does not scrape live shopping sites.
6. **Background analysis:** processes a dataset with the chosen model, saves completed results, reports failures and resumes unfinished records after an interruption. Different models have separate saved results.
7. **Annotation workbench:** creates frozen studies from imported datasets and shows one sentence at a time without ratings or predictions. You assign all ten category states, save drafts, mark sentences complete and export completed labels. Each save has a revision and history record. Conflicting edits are rejected.
8. **Model evaluation:** queues validation comparisons or TF-IDF training from completed labels, lists available models and reads actual experiment reports. Tuple F1 requires the correct aspect and sentiment together. The application does not invent accuracy figures when human labels are missing.

## Models

| Model | What it contributes | Current state |
| --- | --- | --- |
| Rules + VADER | Explicit aspect phrases, clause splitting and sentiment heuristics | Working baseline; all 4,346 source reviews processed |
| Transferred DeBERTa ABSA | Explicit aspect candidates paired with a pretrained transformer sentiment classifier | Installed and verified locally on CPU; no smartphone benchmark yet |
| TF-IDF + logistic classifiers | Learns five states per category from this project's human labels | Training, evaluation and dashboard loading implemented; no real trained artifact yet |

The transferred model is third-party pretrained work. Our implementation supplies smartphone categories, candidate detection, clause pairing, evidence tracking, aggregation, storage, evaluation and the application. Details and attribution are in [the modeling notes](MODELING.md).

## Technology

- **Frontend:** React, TypeScript and Vite. Recharts renders the sentiment chart; Lucide supplies icons.
- **Backend:** Python and FastAPI. Pydantic validates requests and records.
- **Database:** SQLite with numbered, checksum-checked migrations, foreign keys and WAL journaling. Reviews, per-model predictions, jobs and annotation edits persist locally.
- **Text processing:** pysbd for sentences, langdetect for language checks, explicit feature expressions for the baseline/transfer adapter, VADER for baseline sentiment.
- **Classical ML:** scikit-learn for TF-IDF, logistic regression, duplicate grouping and metrics; joblib for trusted local artifacts.
- **Neural inference:** PyTorch, Hugging Face Transformers and SentencePiece. Model weights are downloaded once; prediction uses local files.
- **Verification:** pytest, Ruff, frontend formatting, TypeScript/build checks and GitHub Actions. Optional model weights are not downloaded by CI.

## How it is structured

```text
frontend/src/                 Screens, components, API types and styles
src/smartphone_absa/
  api.py, annotation_api.py   HTTP routes
  domain.py, taxonomy.py     Validated records and shared category definitions
  store.py, migrations/      SQLite queries and schema changes
  jobs.py                    Background processing and recovery
  baseline.py                Rules + VADER
  models/                    Checkpoint download, registry and inference adapters
  annotations.py             Blind sampling, grouped splits and label validation
  workbench.py               Annotation persistence, revisions and export
  experiments.py, metrics.py Training, comparisons and scoring
  data.py, uploads.py         Audited corpus preparation and CSV imports
  cli.py                     Repeatable terminal commands
config/products.json         Explicit smartphone listing selection
RESEARCH_PLAN.md              Research decisions and scope
docs/                        User, data, annotation and operations notes
tests/                       Isolated checks; never used as project gold data
data/, artifacts/            Local corpus, database, labels and weights; Git ignored
```

A request follows `React → FastAPI → model/storage → SQLite → React`. Bulk jobs use one worker and commit each finished review. This is a single-machine application; it does not claim distributed processing or production deployment.

## Data and remaining work

The verified source contains 67,986 historical review rows. Our bounded corpus has 4,346 reviews from 12 selected listings. Automatic language filtering retained 3,819 English and 527 short/uncertain records. The 101-sentence annotation pilot contains training examples only and starts blank.

The dashboard can now create a full study, track partition completion and queue experiments. A 303-sentence full study has been created locally with 199 training, 35 validation and 69 test sentences; it remains blank. The next research dependency is your human annotation. Time a small part of the pilot, check ambiguous decisions, then choose a manageable full sample with frozen validation/test partitions. Only then can we publish model comparisons or decide whether Colab fine-tuning improves the result. Hindi/Hinglish support remains a later extension.
