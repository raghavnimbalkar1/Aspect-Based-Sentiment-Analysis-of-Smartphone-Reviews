ALTER TABLE annotation_tasks ADD COLUMN origin TEXT NOT NULL DEFAULT 'human'
    CHECK (origin IN ('human','assisted'));
