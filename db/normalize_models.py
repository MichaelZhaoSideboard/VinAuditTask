#!/usr/bin/env python3
"""
Normalizes model strings in the listings table using NHTSA canonical model names
as the reference, with fuzzy matching to handle malformed data.

Workflow:
  1. Fetches NHTSA models per make via the vPIC API and caches them in the
     nhtsa_models table (created by 004_add_nhtsa_tables.sql).
  2. Lightly preprocesses each raw model string (HTML decode, trademark strip).
  3. Matches against NHTSA canonicals using two levels:
       a. Token-subset match: NHTSA canonical's tokens are all present in the
          data model — handles trim variants ("Silverado 1500 LTZ" → "Silverado 1500"),
          prefix noise ("New Grand Cherokee" → "Grand Cherokee"), separator variants
          ("Town & Country Touring" → "Town & Country").
          Among all subset matches, the longest (most specific) canonical wins.
       b. Fuzzy fallback (WRatio ≥ 85): handles truncation ("Silverad..." → "Silverado"),
          typos, and other partial matches not caught by subset logic.
  4. Falls back to data-driven prefix collapse for makes with no NHTSA results.

Usage:
    ./normalize_models.py [db_url] [--no-fetch]
    DATABASE_URL=postgresql://... ./normalize_models.py

Run after 004_add_nhtsa_tables.sql has been applied and listings populated.
--no-fetch skips the NHTSA API calls and reuses the existing nhtsa_models table.
"""

from __future__ import annotations

import html
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from collections import defaultdict

import psycopg2
import psycopg2.extras
from rapidfuzz import fuzz, utils
from rapidfuzz import process as fuzz_process

MIN_BASE_LISTINGS = 20
FUZZY_SCORE_THRESHOLD = 85
NHTSA_DELAY = 0.15


def _preprocess_model(model: str) -> str:
    s = html.unescape(model)
    s = re.sub(r'[®™©]', '', s)
    return s.strip()


def _tokenize(s: str) -> frozenset[str]:
    """Lowercase, split on whitespace, strip non-alphanumeric from each token."""
    return frozenset(
        t for t in (re.sub(r'[^a-z0-9]', '', w) for w in s.lower().split())
        if t
    )


def _key_sep(s: str) -> str:
    return re.sub(r'[\s-]', '', s.lower())


def _key_nodash(s: str) -> str:
    return s.lower().replace('-', '')


def _clean_make(make: str) -> str:
    s = html.unescape(make)
    return re.sub(r'[®™©]', '', s).strip()


def _sep_key_make(s: str) -> str:
    return re.sub(r'[\s-]', '', s.lower())


def _fetch_nhtsa_models(make: str) -> list[str]:
    encoded = urllib.parse.quote(make)
    url = f"https://vpic.nhtsa.dot.gov/api/vehicles/GetModelsForMake/{encoded}?format=json"
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            data = json.loads(resp.read().decode())
        return [r["Model_Name"] for r in data.get("Results", []) if r.get("Model_Name")]
    except Exception as e:
        print(f"    Warning: NHTSA fetch failed for '{make}': {e}", file=sys.stderr)
        return []


def _load_nhtsa_from_db(conn) -> dict[str, list[str]]:
    """Load NHTSA models from nhtsa_models table (skips API fetch)."""
    cur = conn.cursor()
    cur.execute("SELECT make, model FROM nhtsa_models")
    result: dict[str, list[str]] = defaultdict(list)
    for make, model in cur.fetchall():
        if model.strip():
            make_key = _sep_key_make(_clean_make(make))
            result[make_key].append(_preprocess_model(model))
    result = {k: list(set(v)) for k, v in result.items()}
    total = sum(len(v) for v in result.values())
    print(f"    Loaded {total:,} NHTSA models from DB ({len(result)} makes).")
    return dict(result)


def _populate_nhtsa_table(conn, canonical_makes: list[str]) -> dict[str, list[str]]:
    """Fetch NHTSA models per make, store in nhtsa_models table."""
    cur = conn.cursor()
    cur.execute("TRUNCATE nhtsa_models")
    conn.commit()

    result: dict[str, list[str]] = {}
    rows_to_insert: list[tuple[str, str]] = []

    print(f"    Fetching NHTSA models for {len(canonical_makes)} distinct makes...")
    for i, make in enumerate(canonical_makes):
        raw_models = _fetch_nhtsa_models(make)
        if raw_models:
            preprocessed = list({_preprocess_model(m) for m in raw_models if m.strip()})
            make_key = _sep_key_make(make)
            result[make_key] = preprocessed
            rows_to_insert.extend((make, m) for m in raw_models if m.strip())
        if (i + 1) % 20 == 0 or (i + 1) == len(canonical_makes):
            print(f"      {i+1}/{len(canonical_makes)} makes fetched...")
        time.sleep(NHTSA_DELAY)

    psycopg2.extras.execute_values(
        cur,
        "INSERT INTO nhtsa_models (make, model) VALUES %s ON CONFLICT DO NOTHING",
        rows_to_insert,
        page_size=5000,
    )
    conn.commit()
    total = sum(len(v) for v in result.values())
    print(f"    Stored {len(rows_to_insert):,} NHTSA entries ({total:,} preprocessed unique across {len(result)} makes).")
    return result


def _match_to_nhtsa(normalized: str, nhtsa_models: list[str]) -> str | None:
    """
    Match a preprocessed model string against NHTSA canonicals.

    1. Token-subset: NHTSA canonical tokens ⊆ data model tokens.
       Among all matches, returns the longest (most specific) canonical.
       Handles: trim variants, "New " prefix, separator variants (&/and), extra words.

    2. WRatio fuzzy fallback (≥ FUZZY_SCORE_THRESHOLD).
       Handles: truncation ("Silverad..." → "Silverado"), minor typos.
    """
    norm_tokens = _tokenize(normalized)

    subset_matches = [c for c in nhtsa_models if _tokenize(c).issubset(norm_tokens)]
    if subset_matches:
        return max(subset_matches, key=lambda c: len(_tokenize(c)))

    result = fuzz_process.extractOne(
        normalized,
        nhtsa_models,
        scorer=fuzz.WRatio,
        processor=utils.default_process,
        score_cutoff=FUZZY_SCORE_THRESHOLD,
    )
    return result[0] if result else None


def _find_base_model_data(normalized: str, candidates: list[str]) -> str:
    """Data-driven fallback: collapse to shortest matching base model."""
    n_key = _key_sep(normalized)
    n_nd = _key_nodash(normalized)
    for candidate in candidates:
        c_key = _key_sep(candidate)
        c_nd = _key_nodash(candidate)
        if n_key == c_key:
            return candidate
        if n_nd.startswith(c_nd + ' '):
            return candidate
        if len(c_key) >= 3 and n_key.startswith(c_key):
            return candidate
    return normalized


def normalize_model_names(conn, skip_fetch: bool = False) -> int:
    cur = conn.cursor()

    print("    Fetching distinct (make, model) pairs with listing counts...")
    cur.execute(
        """
        SELECT make, model, COUNT(*) AS cnt
        FROM listings
        WHERE model IS NOT NULL AND listing_price IS NOT NULL
        GROUP BY make, model
        """
    )
    raw_counts = {(row[0], row[1]): row[2] for row in cur.fetchall()}

    cur.execute("SELECT DISTINCT make, model FROM listings WHERE model IS NOT NULL")
    pairs = cur.fetchall()
    print(f"    Processing {len(pairs):,} distinct (make, model) pairs...")

    # Derive canonical make name per group (most-frequent cleaned variant)
    make_cnt: dict[str, int] = defaultdict(int)
    for (make, _), cnt in raw_counts.items():
        if make:
            make_cnt[make] += cnt

    make_groups: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for make, cnt in make_cnt.items():
        key = _sep_key_make(_clean_make(make))
        make_groups[key][_clean_make(make)] += cnt

    make_canonical: dict[str, str] = {
        key: max(variants, key=lambda v: variants[v])
        for key, variants in make_groups.items()
    }
    unique_canonical_makes = sorted(make_canonical.values())

    nhtsa_by_key = (
        _load_nhtsa_from_db(conn) if skip_fetch
        else _populate_nhtsa_table(conn, unique_canonical_makes)
    )

    # Preprocess all model strings + build data-driven fallback candidates
    preprocessed: list[tuple[str, str, str]] = []
    make_norm_count: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    for make, model in pairs:
        norm = _preprocess_model(model)
        preprocessed.append((norm, make, model))
        if make:
            make_key = _sep_key_make(_clean_make(make))
            make_norm_count[make_key][norm] += raw_counts.get((make, model), 0)

    sorted_make_models: dict[str, list[str]] = {
        make_key: sorted(
            (n for n, cnt in norm_counts.items() if cnt >= MIN_BASE_LISTINGS),
            key=lambda x: (len(_key_sep(x)), x),
        )
        for make_key, norm_counts in make_norm_count.items()
    }

    # Map each (make, model) pair to its normalized name.
    # For makes with NHTSA data: unmatched models get NULL (excluded from dropdowns).
    # For makes without NHTSA data: fall back to data-driven prefix collapse.
    mapping: list[tuple[str | None, str, str]] = []
    nhtsa_matched = data_matched = nhtsa_nulled = unmatched = 0

    for norm, make, model in preprocessed:
        make_key = _sep_key_make(_clean_make(make)) if make else ''

        if make_key in nhtsa_by_key:
            matched = _match_to_nhtsa(norm, nhtsa_by_key[make_key])
            if matched is not None:
                mapping.append((matched, make, model))
                nhtsa_matched += 1
            else:
                mapping.append((None, make, model))
                nhtsa_nulled += 1
            continue

        candidates = sorted_make_models.get(make_key, [])
        if candidates:
            mapping.append((_find_base_model_data(norm, candidates), make, model))
            data_matched += 1
        else:
            mapping.append((norm, make, model))
            unmatched += 1

    print(f"    Matched: {nhtsa_matched:,} via NHTSA, {data_matched:,} data-driven, {nhtsa_nulled:,} nulled (unrecognized), {unmatched:,} verbatim.")

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


def main():
    args = sys.argv[1:]
    skip_fetch = "--no-fetch" in args
    args = [a for a in args if a != "--no-fetch"]

    db_url = (args[0] if args else None) or os.environ.get("DATABASE_URL")
    if not db_url:
        print("Error: pass db_url as argument or set DATABASE_URL.", file=sys.stderr)
        sys.exit(1)

    conn = psycopg2.connect(db_url)
    label = "NHTSA-backed, using cached DB data" if skip_fetch else "NHTSA-backed"
    print(f"Normalizing model names ({label})...")
    updated = normalize_model_names(conn, skip_fetch=skip_fetch)
    print(f"Done — {updated:,} rows normalized.")
    conn.close()


if __name__ == "__main__":
    main()
