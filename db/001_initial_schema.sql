-- Migration: 001_initial_schema
-- Creates the listings table and supporting indexes

CREATE TABLE IF NOT EXISTS listings (
    vin                      TEXT,
    year                     INTEGER,
    make                     TEXT,
    model                    TEXT,
    trim                     TEXT,
    dealer_name              TEXT,
    dealer_street            TEXT,
    dealer_city              TEXT,
    dealer_state             TEXT,
    dealer_zip               TEXT,
    listing_price            NUMERIC,
    listing_mileage          INTEGER,
    used                     BOOLEAN,
    certified                BOOLEAN,
    style                    TEXT,
    driven_wheels            TEXT,
    engine                   TEXT,
    fuel_type                TEXT,
    exterior_color           TEXT,
    interior_color           TEXT,
    seller_website           TEXT,
    first_seen_date          DATE,
    last_seen_date           DATE,
    dealer_vdp_last_seen_date DATE,
    listing_status           TEXT
);

CREATE INDEX IF NOT EXISTS idx_listings_year_make_model
    ON listings (year, make, model);

CREATE INDEX IF NOT EXISTS idx_listings_price
    ON listings (listing_price)
    WHERE listing_price IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_listings_mileage
    ON listings (listing_mileage)
    WHERE listing_mileage IS NOT NULL;
