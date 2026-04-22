from pydantic import BaseModel


class PriceEstimate(BaseModel):
    estimated_price: int
    price_low: int
    price_high: int
    sample_count: int
    mileage_adjusted: bool
