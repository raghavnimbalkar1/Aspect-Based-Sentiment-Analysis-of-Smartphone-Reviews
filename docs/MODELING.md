# Local models and comparison

## Decision for the one-week implementation

We retain the rule baseline and the supervised TF-IDF path. We have also added a transferred ABSA checkpoint so that a neural model can be demonstrated in the local application before a human-labelled smartphone training set exists. This does not complete the planned supervised experiment or establish which model is better.

The research plan's small pair-classifier fine-tuning remains an option after the pilot. An 8 GB M2 Air is sufficient for the verified CPU inference path; training a transformer can move to Colab while the dashboard stays local.

## Checkpoint and attribution

The downloaded checkpoint is [yangheng/deberta-v3-base-absa-v1.1](https://huggingface.co/yangheng/deberta-v3-base-absa-v1.1), pinned to [revision 10c9dff335a44073e1352360c3a7bc54dc58eb01](https://huggingface.co/yangheng/deberta-v3-base-absa-v1.1/tree/10c9dff335a44073e1352360c3a7bc54dc58eb01). Its repository metadata declares the MIT license. The [pinned configuration](https://huggingface.co/yangheng/deberta-v3-base-absa-v1.1/blob/10c9dff335a44073e1352360c3a7bc54dc58eb01/config.json) maps output classes to negative, neutral and positive.

We download an allowlist of configuration, tokenizer and safetensors files. We do not execute the model repository's Python example or load its pickle weights. Download metadata records revision, sizes and SHA-256 hashes; the registry verifies hashes before loading. Inference uses `local_files_only=True`.

The local ID is `deberta-absa-10c9dff3`. It identifies this pinned checkpoint with the first smartphone adapter. Changing candidate detection, pairing, aggregation or tokenizer behaviour requires a new adapter/model ID before regenerating saved results.

## What the adapter does

1. Detect language and split the original review into sentences, preserving character offsets.
2. Split contrast clauses and independently named aspects joined by “and”.
3. Find explicit smartphone feature cues. Pair the local clause with the actual cue, such as `camera` or `battery`.
4. Run the transformer sentiment classifier for each pair. It receives no star rating or human label.
5. Combine opposing positive/negative predictions into mixed sentiment and attach the full source sentence as evidence.

The checkpoint does not predict absent or mixed directly. Absence follows the candidate gate; mixed follows aggregation. Implicit features, cross-sentence references and difficult attachments can be missed. A clause longer than 512 tokens is rejected rather than silently truncated. A failed batch review stays unfinished and is reported by the job.

Softmax scores are uncalibrated model outputs. Averages attached to combined evidence are not probabilities that the final aspect result is correct. No smartphone-domain accuracy is claimed.

## Install and run

From the repository root:

```sh
make model-setup
make build
make run
```

The first command installs optional neural dependencies and downloads roughly 706 MiB of model/tokenizer files into ignored local storage. Allow additional disk space for PyTorch, dependencies and package caches. Setup needs internet; inference does not. If `make setup` removes optional dependencies, run `make model-setup` again; existing model files are reused.

Choose **DeBERTa ABSA · transferred** in the model selector. On **Analyse a review**, enable comparison with Rules + VADER. To verify persistent analysis without a long run, start with a small imported dataset. The 4,346-review corpus is not automatically rerun with the neural model.

On this M2 Air, the initial offline smoke check took about 16 seconds to import dependencies, verify weights and load the model. After initialization, four short illustrative inputs took about 2 seconds on first inference and 46–108 ms on subsequent calls. These observations use different small inputs, include warm-up effects and are not a throughput benchmark. Browser request times can differ. The stored smoke output is local under `artifacts/smoke-tests`; it is not an evaluation report.

## Human evaluation and supervised training

The pilot is training-only. Export completed labels with their manifest. The default evaluator requires human validation; assisted validation is accepted only with the explicit diagnostic option described below. Test always requires human labels. Predictions are never silently substituted as human gold.

To compare installed models on the same frozen validation sentences:

```sh
.venv/bin/absa evaluate-models data/annotations/annotations.csv --manifest data/annotations/annotations.manifest.json --model rules-v1 --model deberta-absa-10c9dff3 --output artifacts/experiments/transfer-validation-001
```

The command includes an always-absent reference, tuple/presence metrics, per-category results, source hashes, model specifications and inference time. It leaves test untouched. `--final-test` explicitly adds test evaluation after model selection.

To train the classical classifier:

```sh
.venv/bin/absa train-tfidf data/annotations/annotations.csv --manifest data/annotations/annotations.manifest.json --output artifacts/experiments/tfidf-001
```

Training fits vocabulary on training sentences only. Each category gets a five-state classifier; a category with only one training state uses a disclosed constant classifier. The artifact's hash determines its ID, and a `model-info.json` makes it discoverable in the dashboard. Only load artifacts produced locally; a checksum verifies identity, not the safety of an unknown joblib file.

Reports become visible on **Model evaluation**. Automated test fixtures exercise these paths in temporary directories and never appear as project experiment results. One annotator's completed labels must be disclosed as single-annotator work; edit history does not constitute inter-annotator agreement.

## Run experiments from the dashboard

The evaluation page can compare one to three installed models or train the fixed TF-IDF baseline. Select a full study after all validation sentences are complete. Training requires human labels or explicit selection of a prepared assisted training set. AI-reviewed validation requires **Use AI-assisted validation (diagnostic only)** as a separate choice. CLI commands accept `--assisted-validation`. Every resulting report identifies the non-independent reference and counts its origins. Test never accepts assisted labels. See [the label protocol](ANNOTATION.md#ai-assisted-validation-review) and [current results](RESULTS.md).

A submission stores a CSV/manifest snapshot under `artifacts/experiment-inputs/<run-id>` and records its hashes in SQLite. The single local worker verifies those files, executes the experiment and writes a new result directory. The report includes snapshot provenance. Active duplicate runs for the same study are rejected. Interrupted runs retain their inputs; start a new run rather than overwriting a result directory.

Inspect a validation row to see tuple precision, recall and F1; presence F1; category-level gold/prediction support; and a five-state confusion matrix. Download the complete JSON report for its configuration and hashes. The interface never requests final test evaluation; the explicit CLI option remains the final-stage route.

New runs also save `predictions.jsonl` with every evaluated category state: sentence/review identity, original text, partition, model, reference label/origin, prediction, reference type and error class. `prediction_artifact` records its hash, row count and per-model/split error counts. Wrong sentiment is a single reviewable error record while contributing both FP and FN to tuple metrics. On the report detail, filter missed aspects, extra aspects or wrong sentiments and download the complete file. Older reports without this artifact still render. Prediction files contain review text and belong in ignored local artifacts.
