# Local operations

Run one backend process per database. Analysis uses one bounded worker; it is intended for a local academic workspace, not multiple concurrent application servers. Use the built React frontend through port 8000 for the demo.

## Persistence

The default database is `data/workspace.sqlite3`. The application enables foreign keys and WAL journaling. The numbered migration files are tracked; their applied checksums are stored in the database. Do not change a migration that has already been applied. Introduce a new numbered migration for schema changes.

To back up a running workspace, use SQLite's backup API rather than copying only the main file while WAL writes may be active:

```sh
python3 - <<'PY'
import sqlite3
from pathlib import Path

target = Path('artifacts/backups/workspace.sqlite3')
target.parent.mkdir(parents=True, exist_ok=True)
with sqlite3.connect('data/workspace.sqlite3') as source:
    with sqlite3.connect(target) as destination:
        source.backup(destination)
print(target)
PY
```

Preserve a valuable backup before upgrades. Generated databases and backups are ignored by Git. No production database credentials or cloud services are required.

## Interrupted jobs

Each completed review analysis is committed independently. **Stop analysis** cancels queued work immediately or lets the current review finish before stopping. **Resume unfinished reviews** processes only records missing results for the current model/taxonomy IDs. The old job remains part of local history. Counts in a retry message describe that attempt, not all earlier results.

On shutdown, queued jobs stop and a running batch finishes its current review. On startup, any previously queued/running jobs are marked interrupted. Run one API process per database. This control applies to dataset analysis, not research training experiments.

**Inspect failed reviews** shows the first 100 recorded failures with source excerpts and reasons. The API supports further pages at `GET /api/datasets/{dataset_id}/jobs/{job_id}/failures?offset=100&limit=100`. Cancellation uses `POST /api/datasets/{dataset_id}/jobs/{job_id}/cancel`. Migration `005_job_control.sql` adds these records and cancellation flags without rewriting existing analyses or annotations. Historical failures have no detailed records.

A failure such as a clause exceeding 512 tokens requires a corrected, shorter review and a new import; retrying identical invalid text will fail again. Other successfully analysed records remain available.

Corpus exports stream the full filtered selection. The browser upload limit remains 10,000 rows, but exports do not impose that limit on larger CLI-loaded datasets. CSV exports add a `brand` column. Branded uploads now use both brand and model for identity; re-imports may therefore create a distinct dataset from versions that used only the model name. Existing datasets are preserved.

## Model changes

The first increment runs `rules-v1` with `smartphone-v1`. A change that alters predictions must use a new model ID, and a taxonomy change must use a new taxonomy version. Persistence keys include both. Preserve old experiment manifests and checkpoints so reported results remain reproducible.

The model selector applies to analysis, dataset counts, jobs, filters, comparisons and exports. Rules, transferred DeBERTa and locally trained TF-IDF artifacts have separate persisted results. The transformer is loaded lazily and reused within one process. Its first load verifies downloaded file hashes. See [model setup](MODELING.md).

Migration `002_annotation_workbench.sql` adds task collections, sentence labels and append-only edit history. An annotation save checks its expected revision in a transaction; a stale browser receives HTTP 409. Completing a sentence requires all ten states and consistent explicit/implicit references. Export includes only completed sentences. Backups preserve these labels together with predictions.

## Verification limits

The current tests and browser checks establish application behaviour and basic baseline semantics. They do not establish ABSA accuracy on an independent human-labeled smartphone test set. The demo corpus is historical, product-balanced, and filtered by automatic language identification. Near-duplicate grouping uses lexical similarity and cannot guarantee removal of all semantic paraphrases.

## Research jobs and workspace isolation

Migration `003_experiment_runs.sql` adds durable experiment history and a constraint allowing one active experiment per study. Study preparation, review batch inference and experiment execution share the single heavy-work queue. Each experiment snapshots labels at submission and checks their hashes before execution. Startup marks unfinished experiment runs interrupted.

`ABSA_ARTIFACTS` overrides the server's model/report/task directory. Pair it with `ABSA_DATABASE` when operating an isolated test workspace, so fixture reports and models cannot appear in the research workspace. The default is the repository's `artifacts` directory. CLI output paths remain explicit command arguments.

## Before a demonstration

After building the dashboard, run `make doctor`. It opens the existing database read-only, checks SQLite integrity/foreign keys/applied migration checksums, checks built entry assets and verifies installed model files. It reports datasets, saved predictions, active jobs, study completion and available experiment reports. It does not migrate, create an empty database, interrupt jobs, save labels or run inference. Exit status 1 means a technical readiness check failed. An optional model that is not installed remains a setup item rather than preventing the rule-based demo.

`demo_ready` describes these local checks. `research_results_ready` remains false until an explicit human-test experiment report exists. Neither field certifies accuracy. Run checks after the build has finished, and avoid CPU benchmarks while batch jobs or other heavy work are running. See [the rehearsal guide](SUBMISSION.md).

Release 1.0.0 validates reports before listing or downloading them. Damaged reports receive a clear diagnostic and do not break valid results. Research readiness also checks human reference origins and complete frozen test coverage. Old test reports without that evidence do not establish readiness. Repeated artifact IDs occupy one model-catalog entry while each training report remains available.

Run `make verify-release` for a separate synthetic workflow workspace, or `make verify-release-neural` after installing the checkpoint. These commands preserve the research database, labels and test partition. The [quality record](QUALITY_ASSURANCE.md) describes the checks and limits. Readiness and QA establish software operation, not independent accuracy.

Assisted training exports live separately under `artifacts/training-assistance`. AI-reviewed validation labels live in the workbench with explicit `origin=assisted`, introduced by additive migration `004_annotation_origin.sql`; prior human rows default to human. Existing human edits were preserved and the database was backed up before applying it. Experiments snapshot inputs and record hashes/origins. Backups should preserve both the database and `artifacts` to retain labels, provenance and trained models.
