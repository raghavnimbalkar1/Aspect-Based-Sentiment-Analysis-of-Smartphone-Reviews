ALTER TABLE jobs ADD COLUMN cancel_requested INTEGER NOT NULL DEFAULT 0
    CHECK (cancel_requested IN (0,1));

CREATE TABLE job_failures (
    job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    review_id TEXT NOT NULL,
    reason TEXT NOT NULL,
    PRIMARY KEY (job_id, review_id)
);
