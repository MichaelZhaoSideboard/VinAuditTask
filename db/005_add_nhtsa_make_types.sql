-- Migration: 005_add_nhtsa_make_types
-- Stores whether each normalized make produces passenger vehicles,
-- populated by normalize_makes.py using the NHTSA vPIC API.

CREATE TABLE IF NOT EXISTS nhtsa_make_types (
    make                   TEXT PRIMARY KEY,
    has_passenger_vehicles BOOLEAN NOT NULL
);
