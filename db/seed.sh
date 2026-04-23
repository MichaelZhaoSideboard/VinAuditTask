#!/usr/bin/env bash
# Populates the listings table from a pipe-delimited inventory file.
#
# Usage:
#   ./seed.sh <data_file> [db_url]
#
# Arguments:
#   data_file  Path to the pipe-delimited inventory .txt file
#   db_url     PostgreSQL connection string (default: $DATABASE_URL env var)
#
# Examples:
#   ./seed.sh inventory-listing-2022-08-17.txt
#   ./seed.sh data.txt "postgresql://user:pass@localhost:5432/vinaudit"
#   DATABASE_URL="postgresql://..." ./seed.sh data.txt

set -euo pipefail

DATA_FILE="${1:-}"
DB_URL="${2:-${DATABASE_URL:-}}"

# --- Validation ---

if [[ -z "$DATA_FILE" ]]; then
    echo "Error: data file argument is required." >&2
    echo "Usage: $0 <data_file> [db_url]" >&2
    exit 1
fi

if [[ ! -f "$DATA_FILE" ]]; then
    echo "Error: file not found: $DATA_FILE" >&2
    exit 1
fi

if [[ -z "$DB_URL" ]]; then
    echo "Error: no database URL provided. Pass it as second argument or set DATABASE_URL." >&2
    exit 1
fi

PSQL="psql $DB_URL"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "==> Seeding listings from: $DATA_FILE"
echo "==> Target database: $DB_URL"
echo ""

# --- Preflight checks ---

if ! command -v python3 &>/dev/null; then
    echo "Error: python3 is required for model normalization." >&2
    exit 1
fi
if ! python3 -c "import psycopg2" 2>/dev/null; then
    echo "Error: psycopg2 is required. Run: pip install -r db/requirements.txt" >&2
    exit 1
fi

# --- Schema migrations ---

echo "[1/5] Applying schema migrations..."
psql "$DB_URL" -f "$SCRIPT_DIR/001_initial_schema.sql"
psql "$DB_URL" -f "$SCRIPT_DIR/002_add_model_normalized.sql"

# --- Load into staging table (all TEXT to avoid type errors from dirty data) ---

echo "[2/5] Creating staging table..."
$PSQL <<'SQL'
DROP TABLE IF EXISTS listings_raw;
CREATE TEMP TABLE listings_raw (
    vin                       TEXT,
    year                      TEXT,
    make                      TEXT,
    model                     TEXT,
    trim                      TEXT,
    dealer_name               TEXT,
    dealer_street             TEXT,
    dealer_city               TEXT,
    dealer_state              TEXT,
    dealer_zip                TEXT,
    listing_price             TEXT,
    listing_mileage           TEXT,
    used                      TEXT,
    certified                 TEXT,
    style                     TEXT,
    driven_wheels             TEXT,
    engine                    TEXT,
    fuel_type                 TEXT,
    exterior_color            TEXT,
    interior_color            TEXT,
    seller_website            TEXT,
    first_seen_date           TEXT,
    last_seen_date            TEXT,
    dealer_vdp_last_seen_date TEXT,
    listing_status            TEXT
);
SQL

# Use E'\x01' (SOH, ASCII 1) as quote char — it never appears in the data,
# which disables CSV quoting logic and avoids misparses from bare \" in values.
echo "[3/5] Copying raw data (this may take a few minutes for large files)..."
$PSQL -c "\copy listings_raw FROM '$DATA_FILE' WITH (FORMAT csv, DELIMITER '|', HEADER true, NULL '', QUOTE E'\x01');"

ROW_COUNT=$($PSQL -t -c "SELECT COUNT(*) FROM listings_raw;" | tr -d ' ')
echo "      Loaded $ROW_COUNT raw rows."

# --- Insert into typed listings table ---

echo "[4/5] Inserting into listings with type coercion..."
$PSQL <<'SQL'
INSERT INTO listings
SELECT
    NULLIF(vin, ''),
    NULLIF(year, '')::INTEGER,
    NULLIF(make, ''),
    NULLIF(model, ''),
    NULLIF(trim, ''),
    NULLIF(dealer_name, ''),
    NULLIF(dealer_street, ''),
    NULLIF(dealer_city, ''),
    NULLIF(dealer_state, ''),
    NULLIF(dealer_zip, ''),
    CASE WHEN listing_price  ~ '^\d+(\.\d+)?$' THEN listing_price::NUMERIC  ELSE NULL END,
    CASE WHEN listing_mileage ~ '^\d+$'          THEN listing_mileage::INTEGER ELSE NULL END,
    CASE WHEN used       = 'TRUE' THEN TRUE WHEN used       = 'FALSE' THEN FALSE ELSE NULL END,
    CASE WHEN certified  = 'TRUE' THEN TRUE WHEN certified  = 'FALSE' THEN FALSE ELSE NULL END,
    NULLIF(style, ''),
    NULLIF(driven_wheels, ''),
    NULLIF(engine, ''),
    NULLIF(fuel_type, ''),
    NULLIF(exterior_color, ''),
    NULLIF(interior_color, ''),
    NULLIF(seller_website, ''),
    CASE WHEN first_seen_date           ~ '^\d{4}-\d{2}-\d{2}$' THEN first_seen_date::DATE           ELSE NULL END,
    CASE WHEN last_seen_date            ~ '^\d{4}-\d{2}-\d{2}$' THEN last_seen_date::DATE            ELSE NULL END,
    CASE WHEN dealer_vdp_last_seen_date ~ '^\d{4}-\d{2}-\d{2}$' THEN dealer_vdp_last_seen_date::DATE ELSE NULL END,
    NULLIF(listing_status, '')
FROM listings_raw
WHERE dealer_state != ''
  AND dealer_state NOT IN ('ON', 'QC', 'AB', 'BC', 'MB', 'SK', 'NS', 'NB', 'NL', 'PE', 'NT', 'YT');
SQL

INSERTED=$($PSQL -t -c "SELECT COUNT(*) FROM listings;" | tr -d ' ')
FILTERED=$(( ROW_COUNT - INSERTED ))
echo "      $INSERTED rows inserted, $FILTERED filtered out (online-only or non-US)."

echo ""
echo "[5/5] Normalizing model names (NHTSA + fuzzy match)..."
python3 "$SCRIPT_DIR/normalize_models.py" "$DB_URL"

echo ""
echo "==> Done."
