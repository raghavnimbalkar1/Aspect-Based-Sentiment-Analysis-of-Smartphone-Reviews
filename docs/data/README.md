# Source verification

`hardening-verification.json` records release 1.2.0's 160 Python tests, three storage tests, 287 integration assertions and browser recovery/import/export checks. It includes results for the eight new review cases, the 42 earlier regressions and the separate 21-case set with its unresolved sarcasm case. These are development checks using synthetic fixtures, not independent accuracy data.

`source-audit.json` was generated from the original version-2 CSV files, downloaded from [Griko Nibras's Kaggle dataset](https://www.kaggle.com/datasets/grikomsn/amazon-cell-phones-reviews/versions/2). The publisher lists CC0. Raw files stay outside version control.

The inspected files contain 720 listings and 67,986 review rows, with 12 empty bodies and 1,095 repeated listing/body combinations after case and whitespace normalisation. The dates span 24 November 2003 to 25 December 2019. None of those counts describes a ready-to-train ABSA dataset: aspect labels are absent.

The explicit listing selection in `config/products.json` keeps smartphone models and distinguishes renewed listings. It is a bounded historical demonstration corpus. It is not a sample of current phone availability or a representative brand ranking. Language identification and exact deduplication have known limits, so their counts and policy are stored in the generated preparation manifest.

`training-assistance-summary.json` records aggregate counts, frozen-study identity, file hashes and the pinned teacher specification for the 199-sentence training-only pseudo-label export. These labels are machine-generated, not human benchmark annotations. No review text or category rows are redistributed with this summary.

`m2-cpu-latency.json` records actual direct-inference timings and deterministic sample hashes/IDs. Its method and limitations are in [PERFORMANCE.md](../PERFORMANCE.md); it contains no accuracy measurements.

`validation-review-summary.json` records the completed 1-human/34-AI-assisted validation review, frozen-decision/export hashes and preservation of the 69 test sentences. `ai-validation-diagnostic.json` records actual model agreement scores, reference origins and artifact hashes. These results use an AI-assisted reference; they are not independent human-evaluated accuracy. See [RESULTS.md](../RESULTS.md).

`model-refinement-diagnostic.json` records the first five-model development comparison after error inspection, the fixed protocol hash, all aggregate results and two-stage training provenance. `m2-refinement-cpu-latency.json` adds the same-sample five-variant latency repeat and discloses shared neural initialization. Neither file contains review text, individual annotation rows or model weights. The 69 test sentences remain unevaluated.

`release-verification.json` records release 1.0.0's 104 automated tests, 245 integration assertions, 14 browser scenarios, environment and unchanged-test checksums. Workflow fixtures are synthetic, isolated and excluded from research results. See [QUALITY_ASSURANCE.md](../QUALITY_ASSURANCE.md) for scope and limitations.

`sentence-review-verification.json` records release 1.1.1's sentence/opinion fix, 137 automated tests, 287 integration assertions and manual dashboard observations for 21 additional inputs. It includes the intended labels and actual output for the unresolved sarcasm case. These written debugging probes are not independent benchmark data.
