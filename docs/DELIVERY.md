# Delivery phases

Research scope approved on 19 October 2026. The one-week plan assumes one implementation lead, an M2 Mac, optional Colab training, and English reviews.

| Phase | Deliverable | Acceptance criteria | Status |
| --- | --- | --- | --- |
| 1 | Data and baseline foundation | Source files verified; repeatable audit/import; versioned taxonomy; annotation export; review-grouped splits; baseline and metric checks | In progress |
| 2 | Local analysis workspace | Persisted datasets/jobs; single and batch analysis; linked filters; aspect charts; comparisons and exports; clean local restart | Planned |
| 3 | Supervised experiments | Independently checked labels; same split for TF-IDF and transformer; reproducible metrics; downloaded checkpoint runs locally | Awaiting annotation corpus |
| 4 | Submission release | Final held-out results, startup guide, browser verification, known limitations, offline rehearsal | Planned |

Every working increment must identify which model it uses. A rule baseline is useful for integration and inspection; its outputs are not human annotations or measured transformer results.

The preferred source is Griko Nibras's [Amazon Cell Phones Reviews, version 2](https://www.kaggle.com/datasets/grikomsn/amazon-cell-phones-reviews/versions/2). Actual file counts and smartphone filtering decisions will be recorded after inspecting the download.
