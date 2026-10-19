# Demo rehearsal and remaining research work

The local application can be demonstrated now. Accuracy results require the pending human annotation and evaluation steps below. Do not use scores from automated-test or browser-fixture workspaces in the report.

## Five-minute walkthrough

| Time | Show | Explain |
| --- | --- | --- |
| 0:00–0:45 | Overview, prepared corpus and aspect chart | Ratings hide feature-level opinions; this dashboard links aggregate counts back to original sentences. The corpus is historical. |
| 0:45–1:45 | Analyse a review, rules/neural comparison | Use an illustrative contrast such as “The camera is excellent, but the battery is terrible.” Show evidence and explain explicit-cue detection and uncalibrated scores. |
| 1:45–2:30 | Review explorer and phone comparison | Follow an aspect/sentiment filter to reviews. Phone comparisons show support and conditions; they are not current buying recommendations. |
| 2:30–3:30 | Annotation, partition and pending-task filters | Ratings/predictions stay hidden. Explain ten states per sentence, draft/completion/history and frozen duplicate-aware partitions. |
| 3:30–5:00 | Model evaluation | Explain human versus AI-assisted references, diagnostic opt-in, training provenance and locked test. Inspect the real diagnostic reports, confusion matrix and an actual prediction error. |

Before the walkthrough, finish `make check`, `make build` and `make doctor`. Start with `make run` or `bash scripts/start.sh`. Verify the selected corpus/model, and open the neural comparison once to load its weights before a live demonstration. The measured cold/warm timings are in [PERFORMANCE.md](PERFORMANCE.md). Keep a local backup of the database and artifacts. No cloud hosting or live download is needed after setup.

## Finish the accuracy study

1. Validation is now complete with 1 human and 34 AI-assisted sentences. Review its notes and disclose this reference origin. It does not provide independent human validation accuracy. A stronger independent validation study would need fresh human judgments without exposure to AI labels.
2. TF-IDF has been trained on 199 training sentences with human-over-pseudo-label precedence. Its installed ID is `tfidf-db3871146fbb`. Reproducing the run requires explicit assisted-training and assisted-validation selections.
3. Rules, TF-IDF and transferred DeBERTa have been compared against the same AI-assisted reference. Inspect category support/errors and the limits in [RESULTS.md](RESULTS.md). Fix the configurations to test before examining test predictions; do not treat diagnostic ranking as strong independent model-selection evidence.
4. Independently complete the 69 test sentences without looking at model predictions. Export completed labels and extract the CSV/manifest to ignored `data/annotations/final`.
5. Evaluate all selected, already fixed model IDs with the explicit final-test command below. Keep output directories immutable and retain source/artifact hashes.

```sh
.venv/bin/absa evaluate-models data/annotations/final/annotations.csv \
  --manifest data/annotations/final/annotations.manifest.json \
  --model rules-v1 --model deberta-absa-10c9dff3 \
  --model tfidf-db3871146fbb --assisted-validation \
  --final-test --output artifacts/experiments/final-test-001
```

Check IDs against `/api/models` if models have changed. `--assisted-validation` permits the existing diagnostic reference; it never permits assisted test labels. Final evaluation requires completed human test labels and does not retrain or tune models. Report tuple micro-F1, presence F1, category support and confusion matrices with sample counts, annotation origins, single-annotator limitations, assisted training and historical coverage. Do not tune from final-test errors and reuse the same test as independent evidence.

## What is complete and what is conditional

The corpus pipeline, local dashboard, model comparison, annotation, trained TF-IDF artifact, auditable diagnostic reports, CI and operating documentation are implemented. The pinned transferred checkpoint runs on CPU. Assisted training and validation origins are recorded separately; existing human edits are preserved.

Independent test annotation/evaluation and stronger model-quality evidence remain outstanding. Smartphone transformer fine-tuning and Hindi/Hinglish remain extensions; transferred inference and pseudo-label training do not complete those extensions.
