CREATE TABLE datasets (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    source TEXT NOT NULL,
    fingerprint TEXT NOT NULL UNIQUE,
    imported_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    accepted INTEGER NOT NULL,
    rejected INTEGER NOT NULL DEFAULT 0,
    manifest_json TEXT NOT NULL
);

CREATE TABLE reviews (
    dataset_id TEXT NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
    id TEXT NOT NULL,
    product_id TEXT NOT NULL,
    product_name TEXT NOT NULL,
    brand TEXT NOT NULL,
    condition TEXT NOT NULL,
    text TEXT NOT NULL,
    date TEXT,
    language TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    PRIMARY KEY (dataset_id, id)
);
CREATE INDEX reviews_product ON reviews(dataset_id, product_id);

CREATE TABLE analyses (
    id INTEGER PRIMARY KEY,
    dataset_id TEXT NOT NULL,
    review_id TEXT NOT NULL,
    model_id TEXT NOT NULL,
    taxonomy_version TEXT NOT NULL,
    supported INTEGER NOT NULL,
    result_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    FOREIGN KEY (dataset_id, review_id) REFERENCES reviews(dataset_id, id) ON DELETE CASCADE,
    UNIQUE (dataset_id, review_id, model_id, taxonomy_version)
);

CREATE TABLE aspects (
    analysis_id INTEGER NOT NULL REFERENCES analyses(id) ON DELETE CASCADE,
    category TEXT NOT NULL,
    sentiment TEXT NOT NULL CHECK (sentiment IN ('positive','negative','neutral','mixed')),
    PRIMARY KEY (analysis_id, category)
);
CREATE INDEX aspects_filter ON aspects(category, sentiment, analysis_id);

CREATE TABLE jobs (
    id TEXT PRIMARY KEY,
    dataset_id TEXT NOT NULL REFERENCES datasets(id),
    model_id TEXT NOT NULL,
    taxonomy_version TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('queued','running','completed','failed','interrupted')),
    total INTEGER NOT NULL,
    processed INTEGER NOT NULL DEFAULT 0,
    failed INTEGER NOT NULL DEFAULT 0,
    error TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
CREATE UNIQUE INDEX jobs_one_active ON jobs(dataset_id,model_id,taxonomy_version)
    WHERE status IN ('queued','running');
