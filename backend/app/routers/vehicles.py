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
        SELECT make
        FROM listings
        WHERE year = $1
          AND make IS NOT NULL
          AND listing_price IS NOT NULL
        GROUP BY make
        HAVING COUNT(*) >= $2
        ORDER BY make
        """,
        year,
        settings.min_make_listings,
    )
    return [r["make"] for r in rows]


@router.get("/models")
async def list_models(
    year: int = Query(..., ge=1900, le=2100),
    make: str = Query(..., min_length=1),
    db: asyncpg.Connection = Depends(get_db),
) -> list[str]:
    rows = await db.fetch(
        """
        SELECT model
        FROM listings
        WHERE year = $1
          AND make = $2
          AND model IS NOT NULL
          AND listing_price IS NOT NULL
        GROUP BY model
        HAVING COUNT(*) >= $3
        ORDER BY model
        """,
        year,
        make,
        settings.min_make_listings,
    )
    return [r["model"] for r in rows]
