import random
from fastapi import APIRouter, Depends, HTTPException, Query
import asyncpg

from app.database import get_db
from app.estimation import calculate_estimate
from app.schemas import PriceEstimate, SampleListing

router = APIRouter(prefix="/api/estimates", tags=["estimates"])

_MIN_SAMPLES = 5
_MAX_SAMPLE_LISTINGS = 100
_MILEAGE_MAX = 300_000


def _clean_mileage(m) -> float | None:
    """Treat 0 and implausibly high mileage as None so they're excluded from regression."""
    if m is None or m == 0 or m > _MILEAGE_MAX:
        return None
    return float(m)


@router.get("", response_model=PriceEstimate)
async def get_estimate(
    year: int = Query(..., ge=1900, le=2100),
    make: str = Query(..., min_length=1),
    model: str = Query(..., min_length=1),
    mileage: int | None = Query(default=None, ge=0, le=500_000),
    db: asyncpg.Connection = Depends(get_db),
) -> PriceEstimate:
    rows = await db.fetch(
        """
        SELECT listing_price, listing_mileage, dealer_city, dealer_state
        FROM listings
        WHERE year = $1
          AND make = $2
          AND model_normalized = $3
          AND listing_price IS NOT NULL
        """,
        year,
        make,
        model,
    )

    if len(rows) < _MIN_SAMPLES:
        raise HTTPException(
            status_code=404,
            detail=f"Not enough data to estimate price for {year} {make} {model}.",
        )

    prices = [float(r["listing_price"]) for r in rows]
    mileages = [_clean_mileage(r["listing_mileage"]) for r in rows]

    estimated, low, high, adjusted = calculate_estimate(prices, mileages, mileage)

    sample_rows = random.sample(rows, min(_MAX_SAMPLE_LISTINGS, len(rows)))
    sample_listings = [
        SampleListing(
            year=year,
            make=make,
            model=model,
            price=round(float(r["listing_price"])),
            mileage=r["listing_mileage"],
            city=r["dealer_city"],
            state=r["dealer_state"],
        )
        for r in sample_rows
    ]

    return PriceEstimate(
        estimated_price=estimated,
        price_low=low,
        price_high=high,
        sample_count=len(rows),
        mileage_adjusted=adjusted,
        sample_listings=sample_listings,
    )
