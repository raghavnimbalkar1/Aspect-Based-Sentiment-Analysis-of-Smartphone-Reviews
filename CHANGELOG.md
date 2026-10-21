# Changelog

## 1.2.0 — 22 October 2026

- Add cooperative stop/resume controls for batch analysis, atomic worker claims and persistent per-review failure details. Shutdown preserves completed work.
- Stream complete CSV/JSON exports without the former 10,000-review cutoff. Include brands in CSV and handle sequential export chunks moving between worker threads.
- Distinguish imported phones by brand and model; show brand labels in filters, comparisons and review cards.
- Improve camera focus attribution, same-sentence omitted predicates and conditional negatives. Retain general phone opinions alongside separate feature sentences.
- Add live-analysis JSON downloads with original input, model identity, evidence and trace.
- Tolerate unavailable or full browser storage, protect annotation edits from import actions, and skip malformed saved-model catalogue metadata.
- Add 26 Python regressions, three storage failure-path tests and eleven real-model cases. Verify batch recovery, annotation history, imports, exports and mobile layouts in an isolated workspace.

The neural weights are unchanged. The live adapter's policy hash changes its model ID. Earlier adapters and recorded research results retain their identities. The known sarcasm failure and pending independent test evaluation remain documented.

## 1.1.1 — 21 October 2026

- Display each source sentence in reading order with individual feature opinions and supporting clauses. Keep review-level aggregation in a separate summary.
- Preserve separate positive and negative clause evidence for the same aspect, including conservative same-sentence omitted references.
- Correct heavy-use versus weight confusion, cheap-material versus price confusion and incidental network use in battery complaints.
- Use an explicit battery mention as the transformer target without inventing an endurance claim from a capacity specification.
- Add 16 automated regressions and record 21 manual dashboard probes, including the remaining sarcasm failure.

## 1.1.0 — 21 October 2026

- Open directly on live-review analysis and select the installed primary DeBERTa adapter.
- Separate live and corpus model choices. Retain typed input across model changes, navigation and refresh within the browser tab.
- Add version 3 smartphone context handling for charging/endurance, signal targets, app speed, punctuation and short English phrases.
- Show the actual candidate/context/decision trace and mark low-score decisions for review. General phone opinions remain separate from the ten aspect categories.
- Add a Models explained workspace, a concise model map and dashboard/code-change rehearsal guidance.
- Add repeatable real-model demo checks while retaining earlier adapters and their recorded results.

## 1.0.0 — 20 October 2026

Initial complete release of the local English smartphone-review analysis application.

- Corpus preparation, CSV import checks, dataset manifests, persistent model-specific batch analysis and filtered exports.
- Review analytics, original sentence evidence, single-review model comparison and phone comparisons with support counts.
- Blind annotation, frozen duplicate-aware partitions, revision history, label origins and completed-label exports.
- Rules + VADER, two versioned DeBERTa adapters and two locally trained TF-IDF variants.
- Reproducible training/comparison reports, validation/test inspection, per-category metrics, confusion matrices and prediction error review.
- Human-only, complete-partition checks for explicitly requested final evaluation. AI-assisted development results remain clearly identified.
- Import, request, model-catalog, report-validation and responsive-layout fixes from the release review.
- Repeatable isolated integration checks, CI, operating guides and actual application screenshots.
- A 52-slide project reference guide with detailed Notes, source references, editable tables/charts and a text reading companion.

Independent human test annotation/evaluation, transformer fine-tuning and Hindi/Hinglish remain research or scope extensions. The release does not claim production deployment or independently established smartphone accuracy.
