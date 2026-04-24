from pydantic import BaseModel


class SampleListing(BaseModel):
    year: int
    make: str
    model: str
    price: int
    mileage: int | None
    used: bool | None
    city: str | None
    state: str | None


class PriceEstimate(BaseModel):
    estimated_price: int
    price_low: int
    price_high: int
    sample_count: int
    mileage_adjusted: bool
    sample_listings: list[SampleListing]
