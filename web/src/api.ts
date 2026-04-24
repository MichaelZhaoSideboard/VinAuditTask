import type { PriceEstimate } from "./types";

async function get<T>(path: string): Promise<T> {
  const res = await fetch(path);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const detail = body.detail;
    const message =
      typeof detail === "string"
        ? detail
        : Array.isArray(detail) && detail.length > 0
          ? detail[0].msg ?? `Request failed (${res.status})`
          : `Request failed (${res.status})`;
    throw new Error(message);
  }
  return res.json();
}

export const fetchYears = (): Promise<number[]> => get("/api/vehicles/years");

export const fetchMakes = (year: number): Promise<string[]> =>
  get(`/api/vehicles/makes?year=${year}`);

export const fetchModels = (year: number, make: string): Promise<string[]> =>
  get(`/api/vehicles/models?year=${year}&make=${encodeURIComponent(make)}`);

export const fetchEstimate = (
  year: number,
  make: string,
  model: string,
  mileage?: number
): Promise<PriceEstimate> => {
  const params = new URLSearchParams({
    year: String(year),
    make,
    model,
  });
  if (mileage !== undefined) params.set("mileage", String(mileage));
  return get(`/api/estimates?${params}`);
};
