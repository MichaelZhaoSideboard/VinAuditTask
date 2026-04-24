import { useEffect, useState } from "react";
import { fetchYears, fetchMakes, fetchModels, fetchEstimate } from "./api";
import { SearchForm } from "./components/SearchForm";
import { EstimateResult } from "./components/EstimateResult";
import { ListingsTable } from "./components/ListingsTable";
import type { PriceEstimate } from "./types";
import "./App.css";

export default function App() {
  const [years, setYears] = useState<number[]>([]);
  const [makes, setMakes] = useState<string[]>([]);
  const [models, setModels] = useState<string[]>([]);

  const [year, setYear] = useState<number | null>(null);
  const [make, setMake] = useState<string | null>(null);
  const [model, setModel] = useState<string | null>(null);
  const [mileage, setMileage] = useState("");

  const [loadingMakes, setLoadingMakes] = useState(false);
  const [loadingModels, setLoadingModels] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const [estimate, setEstimate] = useState<PriceEstimate | null>(null);
  const [lastSearch, setLastSearch] = useState<{ year: number; make: string; model: string } | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchYears().then(setYears).catch(() => {});
  }, []);

  function handleYearChange(y: number | null) {
    setYear(y);
    setMake(null);
    setModel(null);
    setMakes([]);
    setModels([]);
    setEstimate(null);
    setError(null);
    if (!y) return;
    setLoadingMakes(true);
    fetchMakes(y)
      .then(setMakes)
      .catch(() => {})
      .finally(() => setLoadingMakes(false));
  }

  function handleMakeChange(m: string | null) {
    setMake(m);
    setModel(null);
    setModels([]);
    setEstimate(null);
    setError(null);
    if (!m || !year) return;
    setLoadingModels(true);
    fetchModels(year, m)
      .then(setModels)
      .catch(() => {})
      .finally(() => setLoadingModels(false));
  }

  function handleModelChange(m: string | null) {
    setModel(m);
    setEstimate(null);
    setError(null);
  }

  async function handleSubmit() {
    if (!year || !make || !model) return;
    setSubmitting(true);
    setError(null);
    setEstimate(null);
    try {
      const miles = mileage ? Number(mileage) : undefined;
      if (miles !== undefined && miles > 500_000) {
        setError("Mileage must be 500,000 or less.");
        setSubmitting(false);
        return;
      }
      const result = await fetchEstimate(year, make, model, miles);
      setEstimate(result);
      setLastSearch({ year, make, model });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="page">
      <header className="header">
        <h1>VinAudit</h1>
        <p className="tagline">Used car market price estimator</p>
      </header>

      <main className="main">
        <SearchForm
          years={years}
          makes={makes}
          models={models}
          year={year}
          make={make}
          model={model}
          mileage={mileage}
          loadingMakes={loadingMakes}
          loadingModels={loadingModels}
          submitting={submitting}
          onYearChange={handleYearChange}
          onMakeChange={handleMakeChange}
          onModelChange={handleModelChange}
          onMileageChange={setMileage}
          onSubmit={handleSubmit}
        />

        {error && <div className="error-banner">{error}</div>}

        {estimate && lastSearch && (
          <>
            <EstimateResult
              estimate={estimate}
              year={lastSearch.year}
              make={lastSearch.make}
              model={lastSearch.model}
            />
            <ListingsTable
              listings={estimate.sample_listings}
              totalCount={estimate.sample_count}
            />
          </>
        )}
      </main>
    </div>
  );
}
