# Demo rehearsal and remaining research work

The local application can be demonstrated now. Accuracy results require the pending human annotation and evaluation steps below. Do not use scores from automated-test or browser-fixture workspaces in the report.

## Five-minute walkthrough

| Time | Show | Explain |
| --- | --- | --- |
| 0:00–0:45 | Overview, prepared corpus and aspect chart | Ratings hide feature-level opinions; this dashboard links aggregate counts back to original sentences. The corpus is historical. |
| 0:45–1:45 | Analyse a review, rules/neural comparison | Use an illustrative contrast such as “The camera is excellent, but the battery is terrible.” Show evidence and explain explicit-cue detection and uncalibrated scores. |
| 1:45–2:30 | Review explorer and phone comparison | Follow an aspect/sentiment filter to reviews. Phone comparisons show support and conditions; they are not current buying recommendations. |
| 2:30–3:30 | Annotation, partition and pending-task filters | Ratings/predictions stay hidden. Explain ten states per sentence, draft/completion/history and frozen duplicate-aware partitions. |
| 3:30–5:00 | Model evaluation | Explain the human validation requirement, optional assisted training provenance and locked test. Once real reports exist, inspect per-aspect metrics, confusion matrix and an actual prediction error. |

Before the walkthrough, finish `make check`, `make build` and `make doctor`. Start with `make run` or `bash scripts/start.sh`. Verify the selected corpus/model, and open the neural comparison once to load its weights before a live demonstration. The measured cold/warm timings are in [PERFORMANCE.md](PERFORMANCE.md). Keep a local backup of the database and artifacts. No cloud hosting or live download is needed after setup.

## Finish the accuracy study

1. In **Annotation**, choose the 303-sentence smartphone study, **Validation → Still to complete**. Independently label its 35 sentences and review ambiguous notes in a second pass. Keep all ten category decisions per sentence.
2. On **Model evaluation**, train TF-IDF with the separately saved assisted training set explicitly selected, or supply completed human training sentences. The current assisted set covers the frozen 199 training sentences. Report its provenance and label origins.
3. Compare rules, the registered TF-IDF model and transferred DeBERTa on the same human validation set. Inspect category support and errors. Record the selected configuration before examining test predictions. Avoid claiming supported performance for a class with no human examples.
4. Independently complete the 69 test sentences without looking at model predictions. Export completed labels and extract the CSV/manifest to ignored `data/annotations/final`.
5. Evaluate all selected, already fixed model IDs with the explicit final-test command below. Keep output directories immutable and retain source/artifact hashes.

```sh
.venv/bin/absa evaluate-models data/annotations/final/annotations.csv \
  --manifest data/annotations/final/annotations.manifest.json \
  --model rules-v1 --model deberta-absa-10c9dff3 \
  --model tfidf-REPLACE_WITH_INSTALLED_ID \
  --final-test --output artifacts/experiments/final-test-001
```

Replace the TF-IDF placeholder with its actual ID from `/api/models`. CLI final evaluation accepts only adjudicated human validation/test labels. It does not retrain or tune models. Report the exact tuple micro-F1, presence F1, per-category support and confusion matrix; include sample counts, single-annotator limitations, assisted training, historical data and failed/unsupported cases. Archive all predictions locally. Do not alter the model based on final-test errors and then reuse the same test as independent evidence.

## What is complete and what is conditional

The corpus pipeline, local dashboard, persisted jobs/results, model comparison, blind annotation, supervised training workflow, auditable validation reports, CI and operating documentation are implemented. The pinned transferred checkpoint is installed and runs on CPU. The assisted training export is prepared with no changes to human tasks.

Human holdout completion, actual TF-IDF fitting on the chosen training labels, model selection and final accuracy reporting remain conditional on those independent labels. Smartphone transformer fine-tuning and Hindi/Hinglish remain extensions; transferred inference and pseudo-label training do not complete those extensions.
