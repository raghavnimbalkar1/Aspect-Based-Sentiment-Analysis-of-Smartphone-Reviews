# Release quality records

## Release 1.1.0: live-review demo

Verified on 21 October 2026. The current changes focus on new inputs, model clarity and demonstration preparation.

| Check | Result |
| --- | --- |
| Automated tests | 121 passed |
| Ruff, Prettier, TypeScript and production build | Passed |
| Written real-model demo regressions | 42 passed |
| Isolated integration across six installed variants | 288 assertions passed |
| Browser checks | 11 scenarios passed, including model changes, draft retention, general opinions, unsupported text, baseline comparison, cancellation, result focus and narrow layouts |
| Workspace doctor | Demo ready; independent research results still pending |
| Frozen real test partition | 69 blank tasks unchanged from the pre-release backup |

The [machine-readable record](data/live-demo-verification.json) records the model ID, example checksum, browser coverage and test-row checksum. Written examples and synthetic integration fixtures are software checks, not independent accuracy data. All seven workspaces were checked for page overflow at 390 px; the two changed screens were checked again after the layout adjustments. The viewport returned to 1280 × 720, and the checked browser console had no errors or warnings.

The real-model checks exposed charging versus performance confusion, charging versus battery-endurance confusion, missed early battery failure, weak signal targets and app-speed attribution. The version 3 adapter handles those development regressions with context/candidate changes and more appropriate aspect targets. Sentiment still comes from the same pinned DeBERTa weights. The earlier adapters and recorded research comparisons retain their identities.

Some polarity errors remain. For example, the checked phrase “battery life is mediocre” receives neutral with a low model score. The UI marks that decision for review. This is an unresolved prediction limitation, not a corrected label or an accuracy claim. Sarcasm and difficult implicit references also remain outside a reliability guarantee.

See the [model map](MODEL_MAP.md) and [demo/code-change guide](DEMO_PREPARATION.md). The 1.0.0 PowerPoint remains a reference to its dated application snapshot; these guides cover the new live workflow.

## Release 1.0.0

Verified on 20 October 2026. The local English application is feature complete for the documented workflows. Independent human test accuracy remains a separate, unfinished research task.

### Evidence

| Check | Result | Scope |
| --- | --- | --- |
| Automated tests | 104 passed | Models, data validation, metrics, persistence, annotations, experiments and release regressions |
| Ruff, Prettier, TypeScript, production build | Passed | Backend/scripts and compiled dashboard |
| Installed-model integration run | 245 assertions passed | All five installed model variants in a separate synthetic workspace |
| Browser scenarios | 14 passed | Codex in-app browser, default viewport plus 768 px and 390 px checks |
| Workspace doctor | Passed | Built assets, database integrity, foreign keys, migration checksums and model hashes |
| Research test preservation | Passed | All 69 rows have the same before/after checksum and remain unlabelled |

The [machine-readable record](data/release-verification.json) lists every integration assertion, browser scenario, environment and test-row checksum. The assertions include repeated checks across models and reviews; they are not 245 independent benchmark examples. Synthetic fixture scores are excluded from project results.

### Workflow coverage

| Workflow | Checks |
| --- | --- |
| First run | Empty overview, import entry point, unavailable model setup states and empty final-test view |
| CSV import | Native browser file selection, automatic column mapping, preview, valid/invalid rows, duplicates, repeat-import receipt and manifest download |
| Single review | Rule/neural comparison, original evidence, blank input, unsupported language, unknown model and disclosed limitations |
| Batch analysis | All five models, model identity, per-review persistence, zero-work repeat and restart recovery tests |
| Analytics | Per-category counts recomputed from saved predictions, linked chart filtering, three-phone comparison and stable selection slots |
| Explorer/export | Combined filters, original evidence offsets, matching review/summary/export counts and spreadsheet formula handling |
| Annotation | Blank tasks, frozen partitions, hidden predictions/ratings, draft/completion, dirty-navigation guard, pending-list removal, history, stale revisions and export |
| Training | Both TF-IDF methods through API and browser, training-only features, repeated runs, unique artifact IDs and retained provenance |
| Evaluation | Validated reports, damaged-report isolation, per-aspect metrics, confusion matrix, validation/test separation, pagination and integrity-checked prediction downloads |
| Final-test controls | Human-only labels, complete frozen partition, rejection of partial exports and no test inference from the dashboard selector |
| Layout | All six screens at 390 px, loaded overview at 768 px, desktop interaction and no browser console warnings/errors during the recorded pass |

### Defects corrected

- Local requests now use the bound server port, supporting isolated QA workspaces. Malformed or foreign origins receive a controlled rejection.
- A repeated import reports validation counts for the current upload while preserving the existing dataset's original manifest.
- Dataset details expose rejected-row reasons, mapped columns and the downloadable manifest referenced by the import receipt.
- Phone selectors retain their slots when another selection is cleared.
- Cancelled requests cannot replace current data or errors. Changing sections returns to the top of the page.
- The narrow header fits the viewport without horizontal page overflow.
- Report validation rejects incomplete metrics, inconsistent counts and non-finite scores. One damaged report does not break valid results.
- Research readiness requires complete human-test provenance and coverage, rather than trusting a boolean marker.
- Identical artifact IDs appear once in the model catalog, with references to each training run. Different serialized artifacts retain different IDs.
- Final test reports and their error records have a separate inspection view. Selecting it never runs inference.

### Repeat the checks

```sh
make check
make doctor
make verify-release

# After make model-setup, exercise both installed neural adapters too:
make verify-release-neural
```

Each integration run creates a new directory under ignored `artifacts/release-qa`. It copies trusted classical artifacts and reads the installed checkpoint through a link, then uses a separate database and output directory. It does not label, infer or evaluate the real test partition. Choose another `QA_RUN_DIR` if a previous output already exists.

GitHub Actions runs backend checks, the frontend build and a separate integration job with an isolated rules/training workspace. CI does not download the optional neural checkpoint. The local full-model run supplies that additional coverage.

Two initial harness assertions required correction: a zero-work rerun legitimately adds a job-history entry, and a very short Hindi input legitimately follows the documented uncertain-language path. The corrected checks verify unchanged predictions and use a sufficiently long language fixture. Local failed-run artifacts remain available. Model behaviour and research labels were preserved.

### Limits

These checks establish the recorded local workflows, not the absence of every possible defect. They do not cover distributed deployment, multiple API processes sharing a database, every browser, GPU inference or all adversarial inputs. Short non-English text can remain language-unknown and receive a provisional-analysis warning. Existing explicit-cue, sarcasm and opinion-attachment limitations still apply.

The real study still has 1 human and 34 AI-assisted validation sentences, plus 69 unlabelled test sentences. Software release completion does not establish independent research accuracy. See [RESULTS.md](RESULTS.md).
