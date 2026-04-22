from fastapi import APIRouter, Depends, HTTPException, Query
import asyncpg

from app.database import get_db
from app.estimation import calculate_estimate
from app.schemas import PriceEstimate

router = APIRouter(prefix="/api/estimates", tags=["estimates"])

_MIN_SAMPLES = 5


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
        SELECT listing_price, listing_mileage
        FROM listings
        WHERE year = $1
          AND make = $2
          AND model = $3
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
    mileages = [float(r["listing_mileage"]) if r["listing_mileage"] is not None else None for r in rows]

    estimated, low, high, adjusted = calculate_estimate(prices, mileages, mileage)

    return PriceEstimate(
        estimated_price=estimated,
        price_low=low,
        price_high=high,
        sample_count=len(rows),
        mileage_adjusted=adjusted,
    )
