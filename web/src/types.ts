export interface SampleListing {
  year: number;
  make: string;
  model: string;
  price: number;
  mileage: number | null;
  used: boolean | null;
  city: string | null;
  state: string | null;
}

export interface PriceEstimate {
  estimated_price: number;
  price_low: number;
  price_high: number;
  sample_count: number;
  mileage_adjusted: boolean;
  sample_listings: SampleListing[];
}
