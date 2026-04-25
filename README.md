# VinAudit — Used Car Market Price Estimator

VinAudit analyzes real-world used car listing data to produce market value estimates for a given year/make/model. Given a target mileage, it adjusts comparable prices via linear regression before computing the estimate.

## Features

- **Price estimates** — median, low (25th percentile), and high (75th percentile) market prices
- **Mileage-adjusted pricing** — linear regression adjusts comparable listings to a target mileage when sufficient paired data exists
- **Sample listings** — up to 100 randomly selected comparable listings with price, mileage, and location
- **Hierarchical dropdowns** — year → make → model selectors driven by actual data, filtered to exclude noise
- **Low-sample warnings** — flags estimates based on fewer than 30 listings as potentially unreliable

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3, FastAPI, asyncpg |
| Frontend | TypeScript, React 19, Vite |
| Database | PostgreSQL |
| Normalization | rapidfuzz (fuzzy matching), NHTSA vPIC API |

## How Price Estimation Works

The estimation logic lives in [api/app/estimation.py](api/app/estimation.py).

### Without a target mileage

Prices for all matching listings are sorted and percentiles are computed directly using linear interpolation:

- **Low**: 25th percentile
- **Estimated**: 50th percentile (median)
- **High**: 75th percentile

### With a target mileage (mileage-adjusted)

When a target mileage is provided and at least 10 listings have valid mileage data, the algorithm fits a simple linear regression of price on mileage, then adjusts every listing's price to the target mileage before computing percentiles:

```
slope = Σ(mileage - mean_mileage)(price - mean_price) / Σ(mileage - mean_mileage)²
adjusted_price = actual_price - slope × (actual_mileage - target_mileage)
```

Percentiles are then computed on the adjusted prices. The response includes `mileage_adjusted: true` so the frontend can surface a badge indicating the estimate accounts for mileage.

If fewer than 10 listings have valid mileage data, or the slope calculation degenerates (all mileages identical), the algorithm falls back to unadjusted percentiles.

#### Mileage cleaning

Before regression, mileage values of `0`, `null`, or `> 300,000` are treated as missing. These outliers—odometer errors, title washes—would otherwise skew the slope estimate.

## Data Normalization

Raw inventory data contains inconsistent make/model strings ("HONDA", "Honda", "Hond…", "Silverado 1500 LTZ", etc.). Two normalization scripts canonicalize the data before any queries are run. We remove listings with locations in Canada due to currency difference and regional disparities. We also remove non-passenger cars such as trailers and RVs.

### Make normalization ([db/normalize_makes.py](db/normalize_makes.py))

1. Decode HTML entities (®, ™, etc.)
2. Strip separators and lowercase each variant to produce a grouping key
3. Within each group, pick the most frequently occurring cleaned variant as the canonical name
4. Bulk-update `make_normalized` for all rows

### Model normalization ([db/normalize_models.py](db/normalize_models.py))

Three-level matching strategy, applied in order:

**Level 1 — NHTSA token-subset match (preferred)**
- Fetch canonical models from the NHTSA vPIC API for each make
- Tokenize raw model strings into alphanumeric token sets
- Match if a canonical model's tokens are a subset of the raw model's tokens
- Among all matches, pick the longest (most specific) canonical name
- Handles trim variants ("Silverado 1500 LTZ" → "Silverado 1500"), "New " prefixes, separator noise

**Level 2 — Fuzzy WRatio fallback (≥85% score)**
- Uses rapidfuzz for typo and truncation tolerance
- Handles cases like "Silverad..." → "Silverado"

**Level 3 — Data-driven fallback**
- For makes with no NHTSA data, groups raw models by separator-stripped key
- Collapses variants to the shortest matching base model

NHTSA results are cached in a `nhtsa_models` table to avoid repeated API calls on re-runs.

## API Endpoints

All endpoints are read-only (`GET`). The API runs on `http://localhost:8000` by default.

| Endpoint | Description |
|----------|-------------|
| `GET /api/vehicles/years` | All years with at least one priced listing |
| `GET /api/vehicles/makes?year=` | Makes for a year with ≥50 listings |
| `GET /api/vehicles/models?year=&make=` | Models for a year/make with ≥5 listings |
| `GET /api/estimates?year=&make=&model=&mileage=` | Price estimate + sample listings |

The `/api/estimates` endpoint returns a 404 if fewer than 5 listings match the query. A 30-listing threshold is used on the frontend to display a low-confidence warning without blocking the result.

### Minimum listing thresholds

- **Makes**: 50 listings minimum — filters out noise entries like equipment trailers that appear in raw dealer inventory feeds
- **Models**: 5 listings minimum — excludes catch-alls like "Other" and "All Models"

## Database Schema

The primary table is `listings`, seeded from a pipe-delimited inventory export. Key columns:

```
vin, year, make, model, trim,
dealer_name, dealer_city, dealer_state,
listing_price, listing_mileage,
used, certified, style, driven_wheels, engine, fuel_type,
exterior_color, interior_color,
first_seen_date, last_seen_date, listing_status,
model_normalized, make_normalized   -- added by migrations 002-003
```

An index on `(year, make_normalized, model_normalized)` covers the main query pattern.

## Running Locally

**Prerequisites**: PostgreSQL, Python 3.9+, Node 18+

```bash
# 1. Configure the database
cp api/.env.example api/.env
# Edit api/.env and set DATABASE_URL

# 2. Load and normalize data
cd db
bash seed.sh          # runs migrations, seeds listings, normalizes makes & models

# 3. Start both servers
cd ..
bash start.sh         # backend on :8000, frontend on :5173
```

The backend auto-reloads on code changes (uvicorn `--reload`). The frontend uses Vite HMR.

API docs are available at `http://localhost:8000/docs`.

## Limitations and Future Improvements

**Limitations**:
- The initial loading of the dataset into a database and applying the normalization processing can be slow. If the dataset was even larger it would make sense to create a parallel process job to allow for increased performance
- The data normalization process is not perfect. There is a lot of possible scenarios where the scraped vehicle make/model is incorrect and just some maligned string that may contain some vehicle information. There are also certain models that have trims that are distinct that don't collapse well into the base model versus some others that are distinctly different models that are named close enough to another model that it accidentally gets collapsed. There likely needs to be a more robust and engineered way to process incorrect data.

**Improvements**:
- Can add an option to filter by trim of the model. This would likely require a large enough dataset that would allow for an accurate enough estimation for each trim
- Given that the mileage is the biggest factor in determinting estimated price and not year of the car, a possible alternative way to search for estimated price is to allow users to filter by just make, model and mileage. Year does some impact on the average price of a vehicle so we would need to use a different formula for this type of search
- Location is another factor that can impact the estimated value of a vehicle. This would also require a much larger dataset to accurately estimate the value of a given vehicle, but a location filter by state could be useful for someone actually in the market for a vehicle
