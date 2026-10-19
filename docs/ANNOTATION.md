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

Use the 101-sentence training pilot to time the work and refine the guide. The 300-sentence full export above is a starting target, not an accuracy guarantee. Confirm that it contains enough validation/test sentences and relevant classes before drawing conclusions. A tiny evaluation set can produce unstable scores. The workbench deliberately provides no model suggestions; assisted training uses the separate workflow below.

Use **Partition** and **Task status → Still to complete** to work through validation or test directly. Saving a completed sentence removes it from that pending view. Filters and navigation are disabled while there are unsaved changes. General praise without a feature does not imply positive labels for every category; mark only the features that the sentence supports.

## Create a study in the application

Open **Annotation → New study** and choose an imported dataset, a name, a sentence target and either a training pilot or a full study. Preparation runs in the same local work queue as analysis/experiments. Existing labels are preserved. The task CSV and frozen manifest are retained under ignored `artifacts/annotation-tasks`; the editable labels live in SQLite.

The full study has 303 sentences: 199 train, 35 validation and 69 test. Human task labels started blank. The target was 300; the extra sentences keep reviews complete. Partition counts follow grouped reviews and need not be exactly 60/20/20 in a small sample.

On **Model evaluation**, every validation sentence in a study must be complete before an experiment can start. TF-IDF training also needs completed training labels or an explicitly selected assisted set. Each submission freezes a copy of its inputs; subsequent edits cannot change that run. Dashboard experiments calculate validation metrics only.

## Assisted training for the solo workflow

The training assistant is separate from validation review. To make training feasible for one person, the pinned transferred model can generate pseudo labels for the frozen training partition only:

```sh
.venv/bin/absa assist-training --set-id 702b9e3f899067ea52b7088c
```

For a different study, use its ID from `/api/annotations`. The command writes ignored `artifacts/training-assistance/<study-id>/labels.csv`, `manifest.json` and `provenance.json`. It refuses to overwrite an existing export. The prepared local set has 199 sentences / 1,990 category states. Every row is `origin=assisted`, `status=generated`, with the teacher's model ID; no human approval is implied. Hashes and the pinned teacher specification are recorded. Validation/test text is never passed to the teacher by this command. The human workbench and edit history remain unchanged.

On **Model evaluation**, select **Train TF-IDF** and explicitly check **Use saved assisted training labels**. All validation sentences must be complete; assisted validation additionally requires diagnostic mode. A completed human training sentence replaces all ten matching machine labels. The run snapshots the assisted CSV/provenance and human/assisted reference export and checks hashes before execution. Reports and registered-model metadata disclose training origins.

For CLI training, add `--assisted-training artifacts/training-assistance/<study-id>/labels.csv` to `train-tfidf`. This flag never permits assisted validation/test by itself. Teacher errors, missed implicit aspects and class imbalance may be inherited. Disclose both training origins and the evaluation reference's actual provenance.

## AI-assisted validation review

At the user's request, the AI assistant read and labelled the remaining 34 validation sentences directly against the frozen `smartphone-v1` guide. Decisions were frozen before consulting checkpoint/baseline outputs. The existing human validation annotation was preserved. Every sentence retains all ten category states, explicit/implicit references and a rationale; ambiguous interpretations and uncovered features are noted. The original test sentences were not annotated, inferred or changed by this review.

Migration `004_annotation_origin.sql` adds an explicit origin to each saved sentence. These reviewed labels use `origin=assisted` and an AI annotator identifier. Completion means the review was saved, not that a human adjudicated it. The UI shows human/assisted completion separately; exports and edit history preserve origin. Editing an assisted sentence or changing its annotator name cannot silently convert it into independent human labels. Assisted saves to the test partition are rejected.

The local validation collection now contains 1 human and 34 AI-assisted sentences. The default evaluator still rejects assisted references. **Use AI-assisted validation (diagnostic only)** explicitly enables comparison or training against them. CLI equivalents use `--assisted-validation`. Reports record `evaluation_reference.validation.independent=false`, counts and an AI-diagnostic warning. These scores measure agreement with the reference; they are not independent human-evaluated accuracy. Both validation and training opt-ins together still cannot admit assisted test labels.

Frozen review decisions, original-label snapshots and complete exports remain in ignored local data/artifacts. Aggregate provenance is in [validation-review-summary.json](data/validation-review-summary.json). Test annotation remains separate and should not be exposed to predictions before final evaluation.
