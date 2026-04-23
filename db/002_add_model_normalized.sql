-- Migration: 002_add_model_normalized
-- Adds pg_trgm, the canonical_models reference table, and the
-- model_normalized column used for fuzzy-matched model lookups.

CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Canonical make+model pairs sourced from NHTSA vPIC.
CREATE TABLE IF NOT EXISTS canonical_models (
    make  TEXT NOT NULL,
    model TEXT NOT NULL,
    PRIMARY KEY (make, model)
);

-- GIN index powers the % (similarity) operator used during normalization.
CREATE INDEX IF NOT EXISTS idx_canonical_models_model_trgm
    ON canonical_models USING gin (model gin_trgm_ops);

-- Normalized model name populated by normalize_models.py after seeding.
ALTER TABLE listings
    ADD COLUMN IF NOT EXISTS model_normalized TEXT;

-- Replace the old (year, make, model) index with one on model_normalized.
DROP INDEX IF EXISTS idx_listings_year_make_model;

CREATE INDEX IF NOT EXISTS idx_listings_year_make_model_normalized
    ON listings (year, make, model_normalized);
