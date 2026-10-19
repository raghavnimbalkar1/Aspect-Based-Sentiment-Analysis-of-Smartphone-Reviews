# Delivery phases

Research scope approved on 19 October 2026. The one-week plan assumes one implementation lead, an M2 Mac, optional Colab training, and English reviews.

| Phase | Deliverable | Acceptance criteria | Status |
| --- | --- | --- | --- |
| 1 | Data and baseline foundation | Source files verified; repeatable audit/import; versioned taxonomy; annotation export; review-grouped splits; baseline and metric checks | Complete |
| 2 | Local analysis workspace | Persisted datasets/jobs; single and batch analysis; linked filters; aspect charts; comparisons and exports; clean local restart | Complete; verification recorded below |
| 3 | Supervised experiments | Independently checked labels; same split for TF-IDF and transformer; reproducible metrics; downloaded checkpoint runs locally | Awaiting annotation corpus |
| 4 | Submission release | Final held-out results, startup guide, browser verification, known limitations, offline rehearsal | Planned |

Every working increment must identify which model it uses. A rule baseline is useful for integration and inspection; its outputs are not human annotations or measured transformer results.

The preferred source is Griko Nibras's [Amazon Cell Phones Reviews, version 2](https://www.kaggle.com/datasets/grikomsn/amazon-cell-phones-reviews/versions/2). Actual file counts and smartphone filtering decisions will be recorded after inspecting the download.

## First working increment — 19 October 2026

The source checksums match the fixed version-2 files. There are 67,986 review rows and 720 listings. Preparation selected 12 smartphone listings, retained renewed/new condition, applied language filtering and exact duplicate removal, and capped each listing at 400 reviews. The resulting local corpus has 4,346 reviews: 3,819 detected English and 527 short/undetermined-language records retained provisionally. Full counts and policies are in [the preparation summary](data/preparation-summary.json).

All 4,346 records completed baseline processing with zero job failures. This verifies pipeline execution, not model quality. The 101-sentence pilot contains 20 complete source reviews and 1,010 blank category rows from the training partition. It is ready locally at `data/annotations/pilot.csv`; no labels were prefilled.

The React application has been built and inspected in the browser. Single-review analysis correctly separates the contrasting aspects in the documented demonstration example. Chart-to-review navigation, negative-camera filtering, and two-phone comparison were checked against real stored results. Automated API checks cover import → analysis → filtering → export, persistent restart, duplicate imports, and interrupted-job recovery.

The full browser import path was also exercised with five original source reviews: column detection, import, automatic selection of the new dataset, and completion of its batch job. This small verification dataset remains clearly named in the local workspace. Final local verification: 47 backend checks pass, Python static checks pass, frontend formatting and TypeScript/production build pass, and the localhost health endpoint reports the active rule baseline. The dependency installation reported zero npm advisories after removing unused test tooling. GitHub CI is configured separately; its remote run status must be checked after pushing.

No human-annotated benchmark, trained TF-IDF artifact, transformer checkpoint, or held-out model result exists yet. The TF-IDF command and evaluation plumbing are exercised only with isolated test fixtures. The production dashboard does not display those fixture scores.

You confirmed that implementation is a solo responsibility. The next phase will therefore start with the 101-sentence pilot and measured annotation time instead of assuming four additional annotators. We will then choose a manageable evaluation sample and decide whether to use a transferred checkpoint, a small supervised corpus, or explicitly recorded assisted training labels. Independent human evaluation labels remain necessary for accuracy claims. The original 1,000–1,200-sentence target is an expansion goal, not a first-week requirement for one person.
