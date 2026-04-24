-- Migration: 002_add_model_normalized
-- Adds the model_normalized column used for normalized model lookups.

-- Normalized model name populated by normalize_models.py after seeding.
ALTER TABLE listings
    ADD COLUMN IF NOT EXISTS model_normalized TEXT;

-- Replace the old (year, make, model) index with one on model_normalized.
DROP INDEX IF EXISTS idx_listings_year_make_model;

CREATE INDEX IF NOT EXISTS idx_listings_year_make_model_normalized
    ON listings (year, make, model_normalized);
