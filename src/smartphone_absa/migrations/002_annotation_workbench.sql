CREATE TABLE annotation_sets (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    manifest_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE TABLE annotation_tasks (
    set_id TEXT NOT NULL REFERENCES annotation_sets(id),
    sentence_id TEXT NOT NULL,
    position INTEGER NOT NULL,
    task_json TEXT NOT NULL,
    labels_json TEXT NOT NULL DEFAULT '{}',
    annotator TEXT NOT NULL DEFAULT '',
    note TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'draft' CHECK(status IN ('draft','adjudicated')),
    revision INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT,
    PRIMARY KEY (set_id,sentence_id)
);

CREATE TABLE annotation_history (
    set_id TEXT NOT NULL,
    sentence_id TEXT NOT NULL,
    revision INTEGER NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    PRIMARY KEY (set_id,sentence_id,revision),
    FOREIGN KEY (set_id,sentence_id) REFERENCES annotation_tasks(set_id,sentence_id)
);
