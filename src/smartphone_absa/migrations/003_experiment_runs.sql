CREATE TABLE experiment_runs (
    id TEXT PRIMARY KEY,
    set_id TEXT NOT NULL REFERENCES annotation_sets(id),
    kind TEXT NOT NULL CHECK(kind IN ('train_tfidf','compare')),
    status TEXT NOT NULL CHECK(status IN ('queued','running','completed','failed','interrupted')),
    config_json TEXT NOT NULL,
    error TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE UNIQUE INDEX experiment_one_active_per_set ON experiment_runs(set_id)
WHERE status IN ('queued','running');
