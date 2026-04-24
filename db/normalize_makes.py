#!/usr/bin/env python3
"""
Normalizes make strings in the listings table by grouping spelling variants
(e.g. "HARLEY DAVIDSON", "Harley Davidson", "Harley-Davidson&#174;") into a
single canonical name — the most frequently used cleaned variant in each group.

Usage:
    ./normalize_makes.py [db_url]
    DATABASE_URL=postgresql://... ./normalize_makes.py

Run this after 003_add_make_normalized.sql has been applied and the listings
table has been populated.
"""

import html
import os
import re
import sys
from collections import defaultdict

import psycopg2
import psycopg2.extras


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


def main():
    db_url = (sys.argv[1] if len(sys.argv) > 1 else None) or os.environ.get("DATABASE_URL")
    if not db_url:
        print("Error: pass db_url as argument or set DATABASE_URL.", file=sys.stderr)
        sys.exit(1)

    conn = psycopg2.connect(db_url)

    print("Normalizing make names...")
    updated = normalize_make_names(conn)
    print(f"Done — {updated:,} rows normalized.")

    conn.close()


if __name__ == "__main__":
    main()
