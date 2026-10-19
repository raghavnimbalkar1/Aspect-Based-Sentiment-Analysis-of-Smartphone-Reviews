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

Each completed review analysis is committed independently. On application startup, previously queued/running jobs are marked interrupted. Choose **Run analysis** again to process only records missing results for the current model/taxonomy IDs. The old job remains part of the local history.

## Model changes

The first increment runs `rules-v1` with `smartphone-v1`. A change that alters predictions must use a new model ID, and a taxonomy change must use a new taxonomy version. Persistence keys include both. Preserve old experiment manifests and checkpoints so reported results remain reproducible.

The model selector applies to analysis, dataset counts, jobs, filters, comparisons and exports. Rules, transferred DeBERTa and locally trained TF-IDF artifacts have separate persisted results. The transformer is loaded lazily and reused within one process. Its first load verifies downloaded file hashes. See [model setup](MODELING.md).

Migration `002_annotation_workbench.sql` adds task collections, sentence labels and append-only edit history. An annotation save checks its expected revision in a transaction; a stale browser receives HTTP 409. Completing a sentence requires all ten states and consistent explicit/implicit references. Export includes only completed sentences. Backups preserve these labels together with predictions.

## Verification limits

The current tests and browser checks establish application behaviour and basic baseline semantics. They do not establish ABSA accuracy on an independent human-labeled smartphone test set. The demo corpus is historical, product-balanced, and filtered by automatic language identification. Near-duplicate grouping uses lexical similarity and cannot guarantee removal of all semantic paraphrases.
