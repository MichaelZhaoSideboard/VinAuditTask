-- Migration: 003_add_make_normalized
-- Adds the make_normalized column used for normalized make lookups.

ALTER TABLE listings
    ADD COLUMN IF NOT EXISTS make_normalized TEXT;

-- Extend the index to cover make_normalized.
DROP INDEX IF EXISTS idx_listings_year_make_model_normalized;

CREATE INDEX IF NOT EXISTS idx_listings_year_make_model_normalized
    ON listings (year, make_normalized, model_normalized);
