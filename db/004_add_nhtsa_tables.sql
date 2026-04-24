-- Migration: 004_add_nhtsa_tables
-- Stores NHTSA canonical make/model reference data used during normalization.

CREATE TABLE IF NOT EXISTS nhtsa_models (
    make  TEXT NOT NULL,
    model TEXT NOT NULL,
    PRIMARY KEY (make, model)
);
