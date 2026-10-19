# Annotation guide — smartphone-v1

Use the ten categories and five states in [the research plan](../RESEARCH_PLAN.md#4-aspect-categories-and-annotation). Every sentence has ten rows. Fill every `label`, including `absent` for categories that are not discussed. Do not turn missing labels into absent labels automatically.

## Generate tasks

After preparing the source corpus:

```sh
uv run absa annotation-tasks data/processed/reviews.jsonl --output data/annotations/pilot.csv --sentences 100
uv run absa annotation-tasks data/processed/reviews.jsonl --output data/annotations/full.csv --sentences 300 --full
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

## Use the dashboard workbench

Import an untouched blank export and its original manifest:

```sh
.venv/bin/absa annotation-import data/annotations/pilot.csv --manifest data/annotations/pilot.manifest.json --name "Smartphone annotation pilot"
```

Open **Annotation**. Choose a collection, read the sentence and assign each aspect a state. Choose explicit or implicit for present aspects; absent uses no reference. “Mark remaining aspects absent” is an explicit shortcut you control, not a model prediction. Enter a consistent annotator name, then save a draft or mark the sentence complete. Save or discard changes before moving to another sentence.

“Mark complete” records your final decision as `adjudicated`; it does not imply that a second person reviewed it. Since implementation and initial annotation are solo, report single-annotator labels and do not report inter-annotator agreement unless another independent annotator actually participates. Review ambiguous cases in a separate pass.

Completed exports download as a ZIP containing `annotations.csv` and `annotations.manifest.json`. Draft sentences are excluded. The original partitions, duplicate groups and sentence text remain fixed. You can reopen a completed sentence, save a draft to withdraw it from exports, then complete it after review; earlier revisions remain in the database.

Use the 101-sentence training pilot to time the work and refine the guide. The 300-sentence full export above is a starting target, not an accuracy guarantee. Confirm that it contains enough validation/test sentences and relevant classes before drawing conclusions. A tiny evaluation set can produce unstable scores. The workbench deliberately provides no model suggestions; assisted annotation would need a separately recorded training-only workflow.

## Create a study in the application

Open **Annotation → New study** and choose an imported dataset, a name, a sentence target and either a training pilot or a full study. Preparation runs in the same local work queue as analysis/experiments. Existing labels are preserved. The task CSV and frozen manifest are retained under ignored `artifacts/annotation-tasks`; the editable labels live in SQLite.

The full study created during this increment has 303 sentences: 199 train, 35 validation and 69 test, all blank. The target was 300; the extra sentences keep reviews complete. Partition counts follow grouped reviews and need not be exactly 60/20/20 in a small sample.

On **Model evaluation**, every validation sentence in a study must be complete before an experiment can start. TF-IDF training also needs completed training labels. Each submission freezes a copy of completed labels and the manifest; subsequent edits cannot change that run. Dashboard experiments calculate validation metrics only.
