#!/usr/bin/env python3
"""
Normalizes make strings in the listings table by grouping spelling variants
(e.g. "HARLEY DAVIDSON", "Harley Davidson", "Harley-Davidson&#174;") into a
single canonical name — the most frequently used cleaned variant in each group.

Also fetches NHTSA vehicle types for each canonical make and stores them in
the nhtsa_make_types table so the API can filter out non-passenger-vehicle
makes (trailers, RVs, etc.).

Usage:
    ./normalize_makes.py [db_url] [--no-fetch]
    DATABASE_URL=postgresql://... ./normalize_makes.py

Run this after 005_add_nhtsa_make_types.sql has been applied and the listings
table has been populated.
--no-fetch skips the NHTSA API calls and reuses the existing nhtsa_make_types table.
"""

import html
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from collections import defaultdict
from typing import Optional

import psycopg2
import psycopg2.extras

NHTSA_DELAY = 0.15
# NHTSA vehicle type IDs that indicate passenger-carrying road vehicles.
_PASSENGER_TYPE_IDS = {2, 3, 7}  # Passenger Car, Truck, MPV


def _clean_make(make: str) -> str:
    """Decode HTML entities and strip trademark symbols."""
    s = html.unescape(make)
    s = re.sub(r'[®™©]', '', s)
    return s.strip()


def _sep_key(s: str) -> str:
    """Lowercase and strip all dashes/spaces for grouping variants."""
    return re.sub(r'[\s-]', '', s.lower())


def normalize_make_names(conn) -> int:
    cur = conn.cursor()

    print("    Fetching distinct makes with listing counts...")
    cur.execute(
        """
        SELECT make, COUNT(*) AS cnt
        FROM listings
        WHERE make IS NOT NULL AND listing_price IS NOT NULL
        GROUP BY make
        """
    )
    rows = cur.fetchall()
    print(f"    Processing {len(rows):,} distinct make strings...")

    # Group variants by separator-stripped key; track count per cleaned variant.
    groups: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for make, cnt in rows:
        cleaned = _clean_make(make)
        key = _sep_key(cleaned)
        groups[key][cleaned] += cnt

    # Canonical = the cleaned variant with the highest listing count in each group.
    canonical: dict[str, str] = {
        key: max(variants, key=lambda v: variants[v])
        for key, variants in groups.items()
    }

    mapping = [
        (canonical[_sep_key(_clean_make(make))], make)
        for make, _ in rows
    ]

    cur.execute(
        """
        CREATE TEMP TABLE _make_map (
            normalized TEXT,
            make       TEXT
        )
        """
    )
    psycopg2.extras.execute_values(
        cur,
        "INSERT INTO _make_map (normalized, make) VALUES %s",
        mapping,
        page_size=5000,
    )
    conn.commit()

    cur.execute(
        """
        UPDATE listings l
        SET make_normalized = m.normalized
        FROM _make_map m
        WHERE l.make = m.make
        """
    )
    updated = cur.rowcount
    conn.commit()

    cur.execute("DROP TABLE _make_map")
    conn.commit()

    return updated


def _fetch_nhtsa_vehicle_types(make: str) -> Optional[bool]:
    """
    Returns True if NHTSA says this make produces passenger vehicles,
    False if NHTSA has data but none of it is passenger-type, or
    None if the API returned no data (make unknown to NHTSA).
    """
    encoded = urllib.parse.quote(make, safe="")
    url = f"https://vpic.nhtsa.dot.gov/api/vehicles/GetVehicleTypesForMake/{encoded}?format=json"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read())
        results = data.get("Results", [])
        if not results:
            return None
        return any(r.get("VehicleTypeId") in _PASSENGER_TYPE_IDS for r in results)
    except Exception:
        return None


def fetch_and_store_make_types(conn) -> None:
    cur = conn.cursor()

    cur.execute("SELECT DISTINCT make_normalized FROM listings WHERE make_normalized IS NOT NULL")
    makes = [r[0] for r in cur.fetchall()]
    print(f"    Fetching NHTSA vehicle types for {len(makes):,} canonical makes...")

    records: list[tuple[str, bool]] = []
    unknown: list[str] = []
    for i, make in enumerate(makes, 1):
        result = _fetch_nhtsa_vehicle_types(make)
        if result is None:
            unknown.append(make)
        else:
            records.append((make, result))
        if i % 100 == 0:
            print(f"      {i}/{len(makes)} makes processed...")
        time.sleep(NHTSA_DELAY)

    if records:
        psycopg2.extras.execute_values(
            cur,
            """
            INSERT INTO nhtsa_make_types (make, has_passenger_vehicles)
            VALUES %s
            ON CONFLICT (make) DO UPDATE SET has_passenger_vehicles = EXCLUDED.has_passenger_vehicles
            """,
            records,
            page_size=500,
        )
    conn.commit()

    passenger = sum(1 for _, v in records if v)
    non_passenger = len(records) - passenger
    print(f"    Stored: {passenger} passenger, {non_passenger} non-passenger, {len(unknown)} unknown (not stored, will be included by default).")


def main():
    args = sys.argv[1:]
    no_fetch = "--no-fetch" in args
    positional = [a for a in args if not a.startswith("--")]

    db_url = (positional[0] if positional else None) or os.environ.get("DATABASE_URL")
    if not db_url:
        print("Error: pass db_url as argument or set DATABASE_URL.", file=sys.stderr)
        sys.exit(1)

    conn = psycopg2.connect(db_url)

    print("Normalizing make names...")
    updated = normalize_make_names(conn)
    print(f"    {updated:,} rows normalized.")

    if no_fetch:
        print("Skipping NHTSA vehicle type fetch (--no-fetch).")
    else:
        print("Fetching NHTSA vehicle types...")
        fetch_and_store_make_types(conn)

    print("Done.")
    conn.close()


if __name__ == "__main__":
    main()
