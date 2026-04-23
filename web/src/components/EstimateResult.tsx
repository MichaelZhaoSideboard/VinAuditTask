import type { PriceEstimate } from "../types";

function fmt(n: number) {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(n);
}

function roundToHundred(n: number) {
  return Math.round(n / 100) * 100;
}

interface Props {
  estimate: PriceEstimate;
  make: string;
  model: string;
  year: number;
}

const LOW_SAMPLE_THRESHOLD = 30;

export function EstimateResult({ estimate, year, make, model }: Props) {
  const lowSample = estimate.sample_count < LOW_SAMPLE_THRESHOLD;

  return (
    <div className="card result-card">
      <div className="result-label">Estimated Market Price</div>
      <div className="result-vehicle">{year} {make} {model}</div>
      <div className="result-price">{fmt(roundToHundred(estimate.estimated_price))}</div>
      <div className="result-range">
        {fmt(roundToHundred(estimate.price_low))} &ndash; {fmt(roundToHundred(estimate.price_high))}
      </div>
      <div className="result-meta">
        Based on {estimate.sample_count.toLocaleString()} listing{estimate.sample_count !== 1 ? "s" : ""}
        {estimate.mileage_adjusted && " · Mileage adjusted"}
      </div>
      {lowSample && (
        <div className="low-sample-warning">
          Low sample size — this estimate may not accurately reflect market value.
        </div>
      )}
    </div>
  );
}
