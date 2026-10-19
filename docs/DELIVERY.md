# Delivery phases

Research scope approved on 19 October 2026. The one-week plan assumes one implementation lead, an M2 Mac, optional Colab training, and English reviews.

| Phase | Deliverable | Acceptance criteria | Status |
| --- | --- | --- | --- |
| 1 | Data and baseline foundation | Source files verified; repeatable audit/import; versioned taxonomy; annotation export; review-grouped splits; baseline and metric checks | Complete |
| 2 | Local analysis workspace | Persisted datasets/jobs; single and batch analysis; linked filters; aspect charts; comparisons and exports; clean local restart | Complete; verification recorded below |
| 3 | Supervised experiments | Independently checked labels; same split for TF-IDF and transformer; reproducible metrics; downloaded checkpoint runs locally | Local inference and annotation tooling complete; human evaluation pending |
| 4 | Submission release | Final held-out results, startup guide, browser verification, known limitations, offline rehearsal | Planned |

Every working increment must identify which model it uses. A rule baseline is useful for integration and inspection; its outputs are not human annotations or measured transformer results.

The preferred source is Griko Nibras's [Amazon Cell Phones Reviews, version 2](https://www.kaggle.com/datasets/grikomsn/amazon-cell-phones-reviews/versions/2). File counts and smartphone filtering decisions are recorded in the data audit below.

## First working increment — 19 October 2026

The source checksums match the fixed version-2 files. There are 67,986 review rows and 720 listings. Preparation selected 12 smartphone listings, retained renewed/new condition, applied language filtering and exact duplicate removal, and capped each listing at 400 reviews. The resulting local corpus has 4,346 reviews: 3,819 detected English and 527 short/undetermined-language records retained provisionally. Full counts and policies are in [the preparation summary](data/preparation-summary.json).

All 4,346 records completed baseline processing with zero job failures. This verifies pipeline execution, not model quality. The 101-sentence pilot contains 20 complete source reviews and 1,010 blank category rows from the training partition. It is ready locally at `data/annotations/pilot.csv`; no labels were prefilled.

The React application has been built and inspected in the browser. Single-review analysis correctly separates the contrasting aspects in the documented demonstration example. Chart-to-review navigation, negative-camera filtering, and two-phone comparison were checked against real stored results. Automated API checks cover import → analysis → filtering → export, persistent restart, duplicate imports, and interrupted-job recovery.

The full browser import path was also exercised with five original source reviews: column detection, import, automatic selection of the new dataset, and completion of its batch job. This small verification dataset remains clearly named in the local workspace. Final local verification: 47 backend checks pass, Python static checks pass, frontend formatting and TypeScript/production build pass, and the localhost health endpoint reports the active rule baseline. The dependency installation reported zero npm advisories after removing unused test tooling. GitHub CI is configured separately; its remote run status must be checked after pushing.

At the end of the first increment, no human benchmark, trained TF-IDF artifact, transformer checkpoint or held-out result existed. The TF-IDF command and evaluation plumbing are exercised only with isolated test fixtures. The production dashboard does not display those fixture scores.

You confirmed that implementation is a solo responsibility. The next phase will therefore start with the 101-sentence pilot and measured annotation time instead of assuming four additional annotators. We will then choose a manageable evaluation sample and decide whether to use a transferred checkpoint, a small supervised corpus, or explicitly recorded assisted training labels. Independent human evaluation labels remain necessary for accuracy claims. The original 1,000–1,200-sentence target is an expansion goal, not a first-week requirement for one person.

## Modeling workbench increment — 19 October 2026

A pinned transferred DeBERTa ABSA checkpoint now runs locally on CPU. The dashboard selects models, compares the same review against the baseline, and isolates each model's jobs, results, aggregates and exports. Locally trained TF-IDF artifacts are discovered by their content-derived IDs. An evaluation command compares installed models against the same frozen human validation labels; test evaluation remains explicit. This advances phase 3 infrastructure without claiming smartphone fine-tuning or measured accuracy.

The annotation screen imports the existing 101-sentence training pilot with zero prefilled labels. It supports draft/completed states, explicit/implicit references, notes, revision conflict handling, edit history and CSV/manifest export. The previous database was backed up before migration. No human annotations were created during implementation.

Verification covers model isolation, unknown/unavailable models, paired inference/evidence offsets, trained-model loading, annotation validation, persistence, conflicts, export compatibility and locked test evaluation. Browser checks cover local neural comparison, blank task navigation and a persisted neural job on five original source reviews. See the final verification record in the commit/CI history.

Final verification for this increment: 56 backend tests pass; Ruff, frontend formatting, TypeScript and the production build pass. The real checkpoint runs offline on CPU. Five source reviews completed neural batch analysis with zero failures. The browser draft → complete → history flow was checked using a separate temporary database of explicitly synthetic fixtures, keeping the real annotation pilot at zero completed labels.

## Experiment workflow and repository documentation — 19 October 2026

The verified modeling/application branches were merged into `main`. The next increment adds dashboard study creation, partition completion counts and background validation/training runs. Labels and manifests are snapshotted at submission and hash-checked before execution. An additive migration records experiment history and prevents concurrent duplicate runs for a study. On restart, unfinished runs become interrupted without deleting their input snapshots.

All validation sentences must be complete before starting a dashboard experiment; TF-IDF also requires completed training labels. The dashboard never evaluates test. Report inspection now includes exact tuple precision/recall/F1, presence F1, aspect support and a five-state confusion matrix, with JSON download. Newly trained classifiers appear in the model selector.

A full study targeting 300 sentences was created through the real application. It contains 303 sentences from complete reviews: 199 train, 35 validation and 69 test, all blank. The earlier 101-sentence training pilot remains blank. Human annotation and measured smartphone accuracy remain outstanding.

The README now includes five direct app screenshots, installation and optional neural setup, operating instructions, data/model attribution, architecture, evaluation methodology, repository structure and current limitations. Browser checks verified study creation, rejection of incomplete validation, offline neural comparison and the full training → registration → report-inspection flow in a separate synthetic fixture workspace. Fixture scores and models are not research results.
