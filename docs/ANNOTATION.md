# Annotation guide — smartphone-v1

Use the ten categories and five states in [the research plan](../RESEARCH_PLAN.md#4-aspect-categories-and-annotation). Every sentence has ten rows. Fill every `label`, including `absent` for categories that are not discussed. Do not turn missing labels into absent labels automatically.

## Generate tasks

After preparing the source corpus:

```sh
uv run absa annotation-tasks data/processed/reviews.jsonl --output data/annotations/pilot.csv --sentences 100
uv run absa annotation-tasks data/processed/reviews.jsonl --output data/annotations/full.csv --sentences 1200 --full
```

The pilot uses training reviews only. The full export includes train/validation/test partitions. A complete review is retained when the sentence target is reached, so the final count may be slightly larger than requested. Sampling rotates across selected products; it is not a representative population benchmark. Report this product-balanced sampling in the eventual evaluation.

Tasks contain no star ratings, reviewer names, model suggestions, or prefilled sentiment. Short reviews with uncertain detected language stay out of annotation tasks until their language is checked. The sidecar manifest fixes source review partitions, duplicate groups, and sentence text hashes. Keep it with the CSV.

Exact duplicates and near-duplicate review bodies are grouped before partitioning. Near-duplicate detection uses character n-gram TF-IDF cosine similarity at 0.94. This catches highly similar text, not all semantic paraphrases. Independently inspect suspected overlap before final evaluation. Changing the corpus or deduplication settings requires a new versioned manifest.

## Complete a task

Set `label` to `absent`, `positive`, `negative`, `neutral`, or `mixed`. Set `annotator` to a consistent team identifier. Use `reference=explicit` or `implicit` for present aspects. Keep `origin=human` only for independent human judgment. Preserve review IDs, sentence IDs, text, category, split, duplicate group, and taxonomy version.

`neutral` means an aspect is discussed without a clear opinion. `mixed` requires positive and negative evidence about the same category in that sentence. Uncertainty belongs in the note; it is not automatically neutral or mixed. General praise does not apply to every aspect.

Keep independent annotators' copies separate. After disagreement review, create a reconciled file and set `status=adjudicated`. Retain the original copies as local study records. Training rejects blanks, draft labels, incomplete sentence/category sets, changed partitions or text, and non-human evaluation labels.

If uncertain material must be excluded, remove the entire sentence's ten rows from the reconciled file and document the exclusion. Do not selectively remove difficult category rows.

## Train the classical model

```sh
uv run absa train-tfidf data/annotations/reconciled.csv --manifest data/annotations/full.manifest.json --output artifacts/experiments/tfidf-001
```

This trains on the training partition and compares rules, TF-IDF, and always-absent predictions on validation. It does not evaluate test. Add `--final-test` only after model configuration is selected; use a new output directory so old results cannot be overwritten.

The output contains a local `model.joblib` and a metrics JSON with source hashes. Treat model files as trusted local artifacts; do not load files supplied by unknown users. The dashboard will show measured results only when real experiment artifacts are available.
