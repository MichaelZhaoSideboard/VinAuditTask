from fastapi import APIRouter, Depends, Query
import asyncpg

from app.config import settings
from app.database import get_db

router = APIRouter(prefix="/api/vehicles", tags=["vehicles"])


@router.get("/years")
async def list_years(db: asyncpg.Connection = Depends(get_db)) -> list[int]:
    rows = await db.fetch(
        """
        SELECT DISTINCT year
        FROM listings
        WHERE year IS NOT NULL
          AND listing_price IS NOT NULL
        ORDER BY year DESC
        """
    )
    return [r["year"] for r in rows]


@router.get("/makes")
async def list_makes(
    year: int = Query(..., ge=1900, le=2100),
    db: asyncpg.Connection = Depends(get_db),
) -> list[str]:
    rows = await db.fetch(
        """
        SELECT make_normalized
        FROM listings l
        WHERE year = $1
          AND make_normalized IS NOT NULL
          AND listing_price IS NOT NULL
          AND (
              NOT EXISTS (SELECT 1 FROM nhtsa_make_types WHERE make = l.make_normalized)
              OR (SELECT has_passenger_vehicles FROM nhtsa_make_types WHERE make = l.make_normalized)
          )
        GROUP BY make_normalized
        HAVING COUNT(*) >= $2
        ORDER BY make_normalized
        """,
        year,
        settings.min_make_listings,
    )
    return [r["make_normalized"] for r in rows]


@router.get("/models")
async def list_models(
    year: int = Query(..., ge=1900, le=2100),
    make: str = Query(..., min_length=1),
    db: asyncpg.Connection = Depends(get_db),
) -> list[str]:
    rows = await db.fetch(
        """
        SELECT model_normalized
        FROM listings
        WHERE year = $1
          AND make_normalized = $2
          AND model_normalized IS NOT NULL
          AND listing_price IS NOT NULL
          AND LENGTH(model_normalized) > 1
          AND model_normalized NOT IN ('Other', 'All Models')
        GROUP BY model_normalized
        HAVING COUNT(*) >= $3
        ORDER BY model_normalized
        """,
        year,
        make,
        settings.min_model_listings,
    )
    return [r["model_normalized"] for r in rows]
