# Aspect — Smartphone Review Analysis

**Aspect-Based Sentiment Analysis of Smartphone Reviews**

A local research application that turns smartphone reviews into feature-level opinions, with the original sentences kept alongside each prediction. It combines data preparation, model inference, human annotation and reproducible evaluation in one dashboard.

**Release 1.1.1:** live analysis shows sentences in reading order, with separate labels and supporting clauses for each feature opinion. A compact review summary combines those opinions. The app selects **DeBERTa · smartphone context** when installed. The [model map](docs/MODEL_MAP.md) explains the methods; the [demo preparation guide](docs/DEMO_PREPARATION.md) covers the code. Independent human test accuracy remains pending.

Current checks: **137 automated tests**, **42 existing live-review regressions** and **287 integration assertions** across six installed variants passed. Manual dashboard testing covered 21 additional review inputs; 20 matched the intended aspect labels and one sarcastic review remains unresolved. These are development checks, not an accuracy estimate. See the [quality record](docs/QUALITY_ASSURANCE.md).

[![Checks](https://github.com/raghavnimbalkar1/Aspect-Based-Sentiment-Analysis-of-Smartphone-Reviews/actions/workflows/checks.yml/badge.svg?branch=main)](https://github.com/raghavnimbalkar1/Aspect-Based-Sentiment-Analysis-of-Smartphone-Reviews/actions/workflows/checks.yml)
![Python 3.12](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![React and TypeScript](https://img.shields.io/badge/React-TypeScript-3178C6?logo=react&logoColor=white)
![Local inference](https://img.shields.io/badge/Inference-local_CPU-39725c)

![Review intelligence dashboard showing the historical smartphone corpus, aspect sentiment and linked evidence](docs/screenshots/overview.jpg)

[Quick start](#quick-start) · [How it works](#how-it-works) · [Screenshots](#screenshots) · [Models](#models) · [Research workflow](#research-workflow) · [Documentation](#documentation)

For a detailed explanation of the entire project, download the [52-slide reference guide](docs/presentation/Smartphone_ABSA_Reference_Guide.pptx). It covers the dataset, implementation, models, interface and recorded results, with extended explanations and sources in PowerPoint Notes. A [text companion](docs/presentation/STUDY_GUIDE.md) contains the same material for reading and searching.

## Why aspect-based analysis?

An overall rating cannot tell us which part of a phone someone liked. For example:

> The camera is excellent, but the battery is terrible.

| Aspect | Sentiment | Supporting evidence |
| --- | --- | --- |
| Camera | Positive | The camera is excellent |
| Battery | Negative | the battery is terrible. |

The application tracks ten categories: **battery, charging, camera, display, performance and thermals, software, build and design, audio, connectivity, and value**. A mentioned aspect can be positive, negative, neutral or mixed. Annotation and supervised training also use an explicit **absent** state.

## Features

| Workspace | What you can do |
| --- | --- |
| **Overview** | Inspect aspect counts, sentiment distributions and the reviews behind each chart. |
| **Analyse a review** | Read sentence cards with individual feature opinions and exact supporting clauses, inspect the review summary and inference trace, or compare with the baseline. |
| **Models explained** | Distinguish pretrained DeBERTa, the VADER baseline and locally trained TF-IDF methods, including their data and roles. |
| **Review explorer** | Search original reviews, filter by phone/aspect/sentiment and inspect supporting sentences. |
| **Compare phones** | Compare two or three listings, with mention counts, review periods and low-support indicators. |
| **Annotation** | Create a frozen study, filter by partition/completion, label sentences without predictions or ratings, save drafts and export completed labels. |
| **Model evaluation** | Queue validation experiments, train either TF-IDF method, inspect validation or saved final-test reports, and download metrics/predictions. |

CSV import supports column mapping and reports invalid rows and duplicates. Batch analysis preserves completed results and can resume unfinished records. Results, jobs and exports are separated by model and taxonomy version.

**Dataset details and import checks** exposes row rejection reasons, mapped columns and a downloadable manifest. Final-test inspection displays saved results only and never triggers inference.

## Quick start

### Requirements

- Git, a POSIX shell and `make`.
- [uv](https://docs.astral.sh/uv/getting-started/installation/) for the Python environment. The repository selects Python 3.12.
- [Node.js](https://nodejs.org/) 24 or later; `.nvmrc` selects 24.
- Internet for initial dependency/data downloads. The installed application runs locally afterward.

The CPU inference path has been verified on an M2 MacBook Air with 8 GB RAM. A GPU and paid inference API are not required.

```sh
git clone https://github.com/raghavnimbalkar1/Aspect-Based-Sentiment-Analysis-of-Smartphone-Reviews.git
cd Aspect-Based-Sentiment-Analysis-of-Smartphone-Reviews

make setup
make data
make seed
make build
make run
```

Open **[http://localhost:8000](http://localhost:8000)**. The backend serves both the API and the built frontend. Stop it with `Ctrl+C`.

| Command | Purpose |
| --- | --- |
| `make setup` | Install locked Python and frontend dependencies. |
| `make data` | Download the fixed source version, verify checksums and prepare the selected smartphone corpus. |
| `make seed` | Import the prepared corpus idempotently and run the baseline. |
| `make build` | Build the React application. |
| `make run` | Start the saved workspace on port 8000 without downloading dependencies. |
| `make model-setup` | Install optional neural dependencies and download the pinned ABSA checkpoint. |
| `make check` | Run backend tests/lint, frontend formatting checks and the production build. |
| `make doctor` | Check the built dashboard, database, migrations and installed model integrity without changing labels. |
| `make verify-release` | Exercise import, analysis, annotation, training and evaluation in an isolated fixture workspace. |
| `make verify-release-neural` | Repeat integration checks with the installed neural adapters. |
| `make demo-check` | Run the written live-review regressions against the installed primary model. |

To start with your own CSV, skip `make data` and `make seed`, then choose **Import reviews**. After the initial setup, `bash scripts/start.sh` also starts the built application.

[Download the illustrative CSV](examples/smartphone_reviews.csv) to try column mapping without downloading the historical corpus. These ten written examples are demonstration inputs, not evaluation data.

### Enable the neural model

```sh
make model-setup
make run
```

Choose **DeBERTa ABSA · transferred** or **DeBERTa ABSA · domain adapter v2** in the model selector. Both share one approximately 706 MiB checkpoint download and one loaded backbone, in addition to the optional Python dependencies. Inference loads local files and uses CPU by default. Initial loading takes longer than subsequent requests. See [model setup and attribution](docs/MODELING.md).

For the live demo, use **DeBERTa · smartphone context**, the version 3 adapter. It shares those same weights and becomes the initial live selection when available. Corpus analytics retain their own model selector. Typed live text survives model changes, navigation and refresh within the current browser tab.

## How it works

1. **Import and validate.** Preserve original review text, validate optional metadata, detect language and report rejected or repeated rows.
2. **Prepare evidence.** Split reviews into sentences while retaining their character offsets.
3. **Predict aspect sentiment.** The live adapter splits independent opinions within sentences, classifies each context/aspect pair and preserves its exact source span. The review summary combines results per category, keeping the individual opinions available.
4. **Persist and inspect.** Save results in SQLite; use the same review selection for overview charts, the explorer and exports.
5. **Create human labels.** Sample complete reviews, group duplicates before partitioning and freeze task identities in a manifest.
6. **Evaluate reproducibly.** Use frozen human validation labels or explicitly selected AI-assisted diagnostics. Reference origins are recorded; final test evaluation stays separate and human-only.

```mermaid
flowchart LR
    Reviews[Review CSV] --> API[FastAPI service]
    UI[React dashboard] <--> API
    API <--> DB[(SQLite workspace)]
    API --> Queue[Local work queue]
    Queue --> Models[Rules / DeBERTa / TF-IDF]
    Models --> DB
    Queue --> Studies[Frozen annotation studies]
    Studies --> Human[Human / AI-assisted labels]
    Human --> Experiments[Training and validation]
    Experiments --> Reports[Versioned models and JSON reports]
    Reports --> API
```

### Import your own reviews

Only a text column is required. Product, brand, date and overall rating are optional:

```csv
text,product,brand,date,rating
"The camera is sharp, but the battery drains quickly.",Phone A,Example,2026-01-15,3
"The display is bright and charging is fast.",Phone B,Example,2026-01-16,5
```

These rows are illustrative examples, not benchmark data. Map the columns in **Import reviews**, select a model and choose **Run analysis**. UTF-8 uploads are limited to 16 MB, 10,000 rows and 30,000 characters per review. Overall ratings remain metadata; they are never used as aspect labels.

Charts count each review/category once. Phone comparisons use:

```text
net sentiment = 100 × (positive mentions − negative mentions) / all present-state mentions
```

Neutral and mixed mentions remain in the denominator. The comparison screen covers the selected phones across the dataset; overview/explorer exports follow the active review filters.

## Screenshots

The current live-review workflow starts with your own input:

![Live review input with the recommended DeBERTa model selected](docs/screenshots/live-demo-start.png)

![Sentence-level results with separate battery and display opinions](docs/screenshots/sentence-opinions.png)

Separate sentences keep their original order and individual feature labels:

![Three sentences analyzed separately for camera, battery and display](docs/screenshots/sentence-sequence.png)

<details>
<summary><strong>Model roles and training explained</strong></summary>

![Model guide separating pretrained inference, the baseline and locally trained classifiers](docs/screenshots/models-explained.png)

</details>

Screenshots below are captured from the running local application. Corpus views use the rule baseline. The neural comparison uses an illustrative input outside the evaluation set. Annotation shows the actual reviewed validation study; evaluation identifies its AI-assisted reference and development results.

<details>
<summary><strong>Single-review analysis and model comparison</strong></summary>

![Rules and domain adapter v2 analyzing the same illustrative review, with source-sentence evidence](docs/screenshots/domain-comparison.png)

</details>

<details>
<summary><strong>Phone comparison with sample sizes</strong></summary>

![Feature-level comparison of two historical phone listings, including mention counts and review periods](docs/screenshots/phone-comparison.jpg)

</details>

<details>
<summary><strong>Sentence annotation and provenance</strong></summary>

![Completed validation partition showing human and AI-assisted origins alongside the sentence labels](docs/screenshots/annotation.jpg)

</details>

<details>
<summary><strong>Validation experiment workspace</strong></summary>

![Domain adapter results explicitly identified as a development comparison against AI-assisted validation](docs/screenshots/evaluation-refinement.png)

Final-test results remain unavailable until the independent human study is complete:

![Saved final-test results view accurately showing that no final evaluation exists yet](docs/screenshots/final-test-status.png)

</details>

<details>
<summary><strong>Two-stage training with explicit label origins</strong></summary>

![Two-stage TF-IDF selected with separate assisted-training and AI-validation options](docs/screenshots/training-methods.png)

</details>

<details>
<summary><strong>Dataset provenance and review explorer</strong></summary>

![Dataset manifest summary showing source, fingerprint and exclusion reasons](docs/screenshots/dataset-details.png)

![Review explorer with combined aspect and sentiment filters](docs/screenshots/review-explorer.png)

</details>

## Models

| Model | Method | Status |
| --- | --- | --- |
| **DeBERTa · smartphone context** | Version 3 smartphone scope/candidate handling, the pinned DeBERTa classifier, real decision traces and a separate general-opinion output. | Recommended live-review model. Written demo regressions are software checks, not independent accuracy. |
| **Rules + VADER** | Explicit feature cues, clause-local sentiment and documented domain heuristics. | Default baseline; all 4,346 corpus reviews processed. |
| **Transferred DeBERTa ABSA** | Explicit smartphone candidates paired with a pretrained three-state sentiment classifier. Opposing predictions are aggregated as mixed. | Local CPU inference verified; smartphone fine-tuning and independent benchmark results remain pending. |
| **Domain adapter v2** | Expanded smartphone vocabulary, shared-predicate handling and context guards over the same DeBERTa weights. | Available alongside the original adapter; developed using inspected diagnostic errors. |
| **TF-IDF + logistic classifiers** | Training-only word uni/bigrams and one five-state classifier per category. Single-class categories use a disclosed constant classifier. | Trained locally on 199 sentences: 1 human-labelled and 198 pseudo-labelled. Registered as `tfidf-db3871146fbb`; AI-assisted validation results are diagnostic. |
| **Two-stage TF-IDF** | Training-only word/character features; per-category presence detection followed by present-only sentiment classification. | Trained on the same 199 sentences; `tfidf-4e97a73e6f8a`. Both training methods are available in the dashboard. |

The neural checkpoint is **[`yangheng/deberta-v3-base-absa-v1.1`](https://huggingface.co/yangheng/deberta-v3-base-absa-v1.1)**, pinned to revision `10c9dff335a44073e1352360c3a7bc54dc58eb01`. Its published metadata declares MIT licensing. The downloader records file hashes, and inference uses local safetensors without executing repository-supplied Python code.

Our application adds the smartphone taxonomy, candidate pairing, evidence tracking, aggregation, persistence and research workflow. The transferred checkpoint is not presented as a model trained by this project. See [modeling decisions and limitations](docs/MODELING.md).

## Data

The source is Griko Nibras's [Amazon Cell Phones Reviews, version 2](https://www.kaggle.com/datasets/grikomsn/amazon-cell-phones-reviews/versions/2), whose dataset metadata declares CC0.

| Stage | Count |
| --- | ---: |
| Source review rows | 67,986 |
| Source product listings | 720 |
| Selected smartphone listings | 12 |
| Prepared corpus | 4,346 reviews |
| Detected English | 3,819 reviews |
| Short/undetermined language, retained provisionally | 527 reviews |

Preparation uses an explicit listing selection, preserves renewed/new condition, removes exact repeated listing/text rows and caps each listing at 400 reviews. The selected corpus spans July 2016–December 2019. It describes historical reviews and does not rank current phones.

Checksums and aggregate preparation evidence are committed under [docs/data](docs/data/README.md). Raw reviews, generated corpora, databases, labels and weights stay outside Git.

## Research workflow

1. Open **Annotation → New study** and choose an imported dataset. Use a training-only pilot to refine the annotation guide; use a full study for frozen train/validation/test partitions.
2. Label all ten category states for each sentence, including absent. Ratings and model predictions are hidden. Save drafts or mark reviewed decisions complete; edits retain their revision history.
3. Open **Model evaluation** after completing every validation sentence. Choose model comparison or TF-IDF training, then select the original or two-stage training method. Training accepts human or separately prepared assisted labels. AI-assisted validation requires a separate explicit diagnostic-mode selection.
4. Inspect tuple precision/recall/F1, presence F1, category support, the confusion matrix and individual errors. Download the JSON report and per-pair predictions to retain the evidence and source hashes.
5. Select the final model using validation. Final test evaluation requires the explicit CLI option described in [MODELING.md](docs/MODELING.md#human-evaluation-and-supervised-training).

The primary metric is **exact category–sentiment tuple micro-F1**. Detecting the correct aspect with the wrong sentiment counts as both a false positive and a false negative. An always-absent reference is included. Accuracy over predominantly absent categories is not used as the headline result.

A dashboard run freezes completed labels at submission and verifies their hashes before execution. It never evaluates test. Duplicate groups stay in one partition. Single-annotator labels must be reported as such; edit history does not establish inter-annotator agreement.

**Current research status:** validation is complete with **1 human and 34 AI-assisted sentences**. All five model variants have been compared against the same reference. The revised neural adapter reaches **0.750 tuple F1**, versus 0.323 for the original, on this already inspected development sample. This is **not independent accuracy**. The **69 test sentences remain unchanged and unevaluated**. Independent human test annotation/evaluation remains outstanding; smartphone transformer fine-tuning remains an extension. See the [results and limitations](docs/RESULTS.md) and [label protocol](docs/ANNOTATION.md#ai-assisted-validation-review).

## Technology and structure

| Layer | Technology |
| --- | --- |
| Interface | React, TypeScript, Vite, Recharts, Lucide |
| API and validation | Python, FastAPI, Pydantic |
| Persistence | SQLite, WAL journaling, numbered/checksum-checked migrations |
| Text processing | pysbd, langdetect, explicit feature expressions, VADER |
| Classical ML | scikit-learn, TF-IDF, logistic regression, joblib |
| Neural inference | PyTorch, Transformers, SentencePiece, safetensors |
| Verification | pytest, Ruff, Prettier, TypeScript, GitHub Actions |

```text
frontend/src/               Dashboard views, components and API types
src/smartphone_absa/
  api.py                   Review analysis and dataset routes
  annotation_api.py        Blind annotation routes
  research_api.py          Study creation, experiment runs and reports
  store.py, migrations/    SQLite persistence and schema upgrades
  baseline.py, models/     Model registry and inference adapters
  annotations.py           Sampling, duplicate grouping and frozen splits
  workbench.py             Label edits, conflicts, history and export
  research.py              Study preparation and immutable experiment inputs
  experiments.py           TF-IDF training and model comparisons
  assistance.py            Training-only generated labels and provenance
  predictions.py           Auditable per-pair predictions and error types
  diagnostics.py           Read-only readiness checks and latency measurement
  metrics.py               Exact tuple and presence metrics
  data.py, uploads.py      Verified corpus preparation and CSV validation
  cli.py                   Repeatable command-line workflows
config/products.json       Reviewed source-listing selection
docs/                      Research, guides, audit evidence and screenshots
tests/                     Isolated behavior, persistence and leakage checks
data/, artifacts/          Generated local files; ignored by Git
```

## Development and operations

```sh
make check
```

For separate development servers, run `make dev-api` and `make dev-ui` in two terminals, then open [localhost:5173](http://localhost:5173). The frontend proxies API requests to port 8000. Interactive API documentation is available at [localhost:8000/docs](http://localhost:8000/docs).

The default database is `data/workspace.sqlite3`; set `ABSA_DATABASE` and `ABSA_ARTIFACTS` to isolate another server workspace. Run one API process per database. Heavy background jobs share one local worker. Back up valuable labels before upgrades; introduce new numbered migrations instead of editing applied ones.

A model behavior change requires a new model ID before reprocessing data. Local TF-IDF IDs derive from their artifacts. Only load trusted local joblib artifacts. See [operations and backups](docs/OPERATIONS.md) and [contribution guidance](CONTRIBUTING.md).

CPU latency was measured on the M2 Air using 16 frozen source reviews and 48 warm requests per model. In the 20 October five-variant repeat, domain adapter v2 has a **60.8 ms median / 230.8 ms p95**, and two-stage TF-IDF **2.3 / 3.5 ms**. Loading the original neural backbone took 4.5 seconds, followed by a separate 2.3-second first inference; the revised adapter shares that loaded backbone. These measurements exclude HTTP/UI/database work and describe responsiveness, not accuracy or concurrent capacity. The [method and full records](docs/PERFORMANCE.md) include the original measurement and disclose candidate-free inputs and shared initialization.

### Limits

- English is supported first. Short text can have uncertain language detection; Hindi/Hinglish remains a later extension.
- Explicit candidate detection can miss implicit features, sarcasm, cross-sentence references and difficult opinion attachment. Neural clauses over 512 tokens are rejected rather than silently truncated.
- Prediction scores are model-specific and uncalibrated. Sample sizes, historical coverage and renewed listings affect comparisons.
- This is a single-machine research workspace. It does not claim distributed processing, multi-user deployment or production-scale model accuracy.

## Documentation

- [Detailed project reference guide and reading companion](docs/presentation/README.md)
- [Which model does what](docs/MODEL_MAP.md)
- [Dashboard rehearsal and code-change preparation](docs/DEMO_PREPARATION.md)
- [Research plan and sources](RESEARCH_PLAN.md)
- [Application walkthrough and architecture](docs/APP_GUIDE.md)
- [Annotation protocol](docs/ANNOTATION.md)
- [Model setup, attribution and evaluation commands](docs/MODELING.md)
- [Data audit and preparation evidence](docs/data/README.md)
- [Delivery phases and verification record](docs/DELIVERY.md)
- [Local operations and database backups](docs/OPERATIONS.md)
- [Demo rehearsal and final evaluation checklist](docs/SUBMISSION.md)
- [CPU performance measurement](docs/PERFORMANCE.md)
- [Review of alternative labelled datasets](docs/BENCHMARK_DATA_REVIEW.md)
- [AI-assisted validation diagnostic and limitations](docs/RESULTS.md)
- [Release quality checks and their scope](docs/QUALITY_ASSURANCE.md)

Dataset and pretrained-model licensing are documented with their sources above. Third-party libraries retain their own licenses; their use does not assign a license to this repository's original code.
