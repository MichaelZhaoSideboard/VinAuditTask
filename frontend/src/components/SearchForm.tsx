interface Props {
  years: number[];
  makes: string[];
  models: string[];
  year: number | null;
  make: string | null;
  model: string | null;
  mileage: string;
  loadingMakes: boolean;
  loadingModels: boolean;
  submitting: boolean;
  onYearChange: (year: number | null) => void;
  onMakeChange: (make: string | null) => void;
  onModelChange: (model: string | null) => void;
  onMileageChange: (mileage: string) => void;
  onSubmit: () => void;
}

export function SearchForm({
  years, makes, models,
  year, make, model, mileage,
  loadingMakes, loadingModels, submitting,
  onYearChange, onMakeChange, onModelChange, onMileageChange,
  onSubmit,
}: Props) {
  const canSubmit = year !== null && make !== null && model !== null && !submitting;

  function handleMileage(e: React.ChangeEvent<HTMLInputElement>) {
    const val = e.target.value.replace(/\D/g, "");
    onMileageChange(val);
  }

  return (
    <div className="card">
      <h2 className="card-title">Find your car&rsquo;s market value</h2>
      <div className="form-row">
        <div className="field">
          <label htmlFor="year">Year</label>
          <select
            id="year"
            value={year ?? ""}
            onChange={(e) => onYearChange(e.target.value ? Number(e.target.value) : null)}
          >
            <option value="">Select year</option>
            {years.map((y) => (
              <option key={y} value={y}>{y}</option>
            ))}
          </select>
        </div>

        <div className="field">
          <label htmlFor="make">Make</label>
          <select
            id="make"
            value={make ?? ""}
            disabled={!year || loadingMakes}
            onChange={(e) => onMakeChange(e.target.value || null)}
          >
            <option value="">{loadingMakes ? "Loading…" : "Select make"}</option>
            {makes.map((m) => (
              <option key={m} value={m}>{m}</option>
            ))}
          </select>
        </div>

        <div className="field">
          <label htmlFor="model">Model</label>
          <select
            id="model"
            value={model ?? ""}
            disabled={!make || loadingModels}
            onChange={(e) => onModelChange(e.target.value || null)}
          >
            <option value="">{loadingModels ? "Loading…" : "Select model"}</option>
            {models.map((m) => (
              <option key={m} value={m}>{m}</option>
            ))}
          </select>
        </div>

        <div className="field">
          <label htmlFor="mileage">Mileage <span className="optional">(optional)</span></label>
          <input
            id="mileage"
            type="text"
            inputMode="numeric"
            placeholder="e.g. 45000"
            value={mileage}
            onChange={handleMileage}
          />
        </div>
      </div>

      <div className="form-footer">
        <button className="btn-primary" disabled={!canSubmit} onClick={onSubmit}>
          {submitting ? "Estimating…" : "Get Estimate"}
        </button>
      </div>
    </div>
  );
}
