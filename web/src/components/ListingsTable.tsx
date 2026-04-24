import type { SampleListing } from "../types";

function fmtPrice(n: number) {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(n);
}

function fmtMileage(n: number | null, used: boolean | null) {
  if (n !== null) return n.toLocaleString("en-US") + " mi";
  return used === false ? "New" : "N/A";
}

function fmtLocation(city: string | null, state: string | null) {
  if (city === "*" || state === "*") return "Online Only";
  if (city && state) return `${city}, ${state}`;
  return city ?? state ?? "—";
}

interface Props {
  listings: SampleListing[];
  totalCount: number;
}

export function ListingsTable({ listings, totalCount }: Props) {
  return (
    <div className="card">
      <h3 className="card-title">
        Sample Listings
        <span className="sample-count">
          {listings.length} of {totalCount.toLocaleString()}
        </span>
      </h3>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Year</th>
              <th>Make &amp; Model</th>
              <th>Price</th>
              <th>Mileage</th>
              <th>Location</th>
            </tr>
          </thead>
          <tbody>
            {listings.map((l, i) => (
              <tr key={i}>
                <td>{l.year}</td>
                <td>{l.make} {l.model}</td>
                <td>{fmtPrice(l.price)}</td>
                <td>{fmtMileage(l.mileage, l.used)}</td>
                <td>{fmtLocation(l.city, l.state)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
