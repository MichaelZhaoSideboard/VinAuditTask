#!/usr/bin/env python3
"""
Populates canonical_models from the NHTSA vPIC API, then normalizes
model strings in the listings table by stripping junk and applying
title case — preserving trim-level granularity.

Usage:
    ./normalize_models.py [db_url]
    DATABASE_URL=postgresql://... ./normalize_models.py

Run this after 002_add_model_normalized.sql has been applied and
the listings table has been populated.
"""

import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

import psycopg2
import psycopg2.extras

NHTSA_BASE = "https://vpic.nhtsa.dot.gov/api/vehicles"
REQUEST_DELAY = 0.15  # seconds between NHTSA calls
MIN_LISTINGS = 5      # skip makes with fewer priced listings (can't estimate anyway)

# Strips VIN-like tokens (8+ non-whitespace chars containing at least one digit)
# and everything after them. e.g. "4t1c11ak1lu331954", "A279922a".
_VIN_RE = re.compile(r'\s+\S*\d\S{6,}.*$')

# Strips "For Sale In/Near/At ..." location noise and everything after.
_FOR_SALE_RE = re.compile(r'\s+for\s+sale\b.*$', re.IGNORECASE)


def _preprocess_model(model: str) -> str:
    """Strip junk patterns and apply title case, preserving trim granularity."""
    s = _VIN_RE.sub('', model)
    s = _FOR_SALE_RE.sub('', s)
    return s.strip().title()


# ---------------------------------------------------------------------------
# NHTSA helpers
# ---------------------------------------------------------------------------

def _fetch_nhtsa_models(make: str) -> list[str]:
    url = f"{NHTSA_BASE}/GetModelsForMake/{urllib.parse.quote(make)}?format=json"
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            data = json.loads(resp.read())
            return [r["Model_Name"] for r in data.get("Results", []) if r.get("Model_Name")]
    except (urllib.error.URLError, json.JSONDecodeError, KeyError) as exc:
        print(f"    Warning: NHTSA lookup failed for '{make}': {exc}", file=sys.stderr)
        return []


def fetch_canonical_models(conn) -> int:
    """Query NHTSA for each estimatable make and insert into canonical_models."""
    cur = conn.cursor()

    cur.execute(
        """
        SELECT make
        FROM listings
        WHERE make IS NOT NULL AND listing_price IS NOT NULL
        GROUP BY make
        HAVING COUNT(*) >= %s
        ORDER BY make
        """,
        (MIN_LISTINGS,),
    )
    makes = [row[0] for row in cur.fetchall()]
    print(f"    Querying NHTSA for {len(makes)} makes...")

    total = 0
    for i, make in enumerate(makes, 1):
        models = _fetch_nhtsa_models(make)
        if models:
            psycopg2.extras.execute_values(
                cur,
                "INSERT INTO canonical_models (make, model) VALUES %s ON CONFLICT DO NOTHING",
                [(make, m) for m in models],
            )
            total += cur.rowcount

        if i % 20 == 0 or i == len(makes):
            conn.commit()
            print(f"    [{i}/{len(makes)}] processed — {total} canonical models so far")

        time.sleep(REQUEST_DELAY)

    conn.commit()
    return total


# ---------------------------------------------------------------------------
# Preprocessing normalization
# ---------------------------------------------------------------------------

def normalize_model_names(conn) -> int:
    """
    Normalizes model strings by stripping VINs and location noise, then
    applying title case. Operates on distinct (make, model) pairs to avoid
    processing 4.7M rows individually, then bulk-updates via a temp table.

    Preserves trim-level granularity — "Camry SE" stays "Camry Se",
    it is NOT collapsed into "Camry".

    Returns the number of rows updated.
    """
    cur = conn.cursor()

    print("    Fetching distinct model strings...")
    cur.execute(
        "SELECT DISTINCT make, model FROM listings WHERE model IS NOT NULL"
    )
    pairs = cur.fetchall()
    print(f"    Processing {len(pairs):,} distinct (make, model) pairs...")

    mapping = [
        (_preprocess_model(model), make, model)
        for make, model in pairs
    ]

    cur.execute(
        """
        CREATE TEMP TABLE _model_map (
            normalized TEXT,
            make       TEXT,
            model      TEXT
        )
        """
    )
    psycopg2.extras.execute_values(
        cur,
        "INSERT INTO _model_map (normalized, make, model) VALUES %s",
        mapping,
        page_size=5000,
    )
    conn.commit()

    cur.execute(
        """
        UPDATE listings l
        SET model_normalized = m.normalized
        FROM _model_map m
        WHERE l.make = m.make AND l.model = m.model
        """
    )
    updated = cur.rowcount
    conn.commit()

    cur.execute("DROP TABLE _model_map")
    conn.commit()

    return updated


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    db_url = (sys.argv[1] if len(sys.argv) > 1 else None) or os.environ.get("DATABASE_URL")
    if not db_url:
        print("Error: pass db_url as argument or set DATABASE_URL.", file=sys.stderr)
        sys.exit(1)

    conn = psycopg2.connect(db_url)

    print("[1/2] Fetching canonical models from NHTSA vPIC...")
    inserted = fetch_canonical_models(conn)
    print(f"    Done — {inserted} new canonical models inserted.\n")

    print("[2/2] Normalizing model names (preprocessing + title case)...")
    updated = normalize_model_names(conn)
    print(f"    Done — {updated:,} rows normalized.")

    conn.close()


if __name__ == "__main__":
    main()
