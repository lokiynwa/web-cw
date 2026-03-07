import { useEffect, useState } from "react";
import { API_BASE_URL } from "../config.js";
import { ApiError, apiClient } from "../lib/apiClient.js";

const DEFAULT_CITY = "Leeds";
const FALLBACK_CITY_OPTIONS = [DEFAULT_CITY];
const AFFORDABILITY_COMPONENTS = "rent,pint,takeaway";
const API_KEY_SESSION_STORAGE_KEY = "demo_contributor_api_key";
const CITY_DISCOVERY_MIN_SAMPLE_SIZE = 10;

function formatMetric(value) {
  if (value === null || value === undefined) {
    return "N/A";
  }
  return Number(value).toFixed(2);
}

function loadApiKeyFromSession() {
  try {
    return sessionStorage.getItem(API_KEY_SESSION_STORAGE_KEY) || "";
  } catch {
    return "";
  }
}

function validateSubmissionForm(form, apiKey) {
  const errors = {};
  const trimmedKey = apiKey.trim();

  if (!trimmedKey) {
    errors.apiKey = "API key is required for submission.";
  }

  if (!form.submissionType) {
    errors.submissionType = "Submission type is required.";
  }

  if (!form.city.trim()) {
    errors.city = "City is required.";
  }

  if (!form.amount.trim()) {
    errors.amount = "Amount is required.";
  } else if (!/^\d+(\.\d{1,2})?$/.test(form.amount.trim())) {
    errors.amount = "Amount must be a valid GBP value with up to 2 decimals.";
  } else {
    const numericAmount = Number(form.amount);
    if (!Number.isFinite(numericAmount) || numericAmount <= 0) {
      errors.amount = "Amount must be greater than 0.";
    }
  }

  if (form.area.trim().length > 120) {
    errors.area = "Area must be 120 characters or fewer.";
  }

  if (form.evidenceNote.trim().length > 4000) {
    errors.evidenceNote = "Evidence note must be 4000 characters or fewer.";
  }

  return errors;
}

export function DashboardPage() {
  const [cityOptions, setCityOptions] = useState(FALLBACK_CITY_OPTIONS);
  const [city, setCity] = useState(DEFAULT_CITY);
  const [cityOptionsLoading, setCityOptionsLoading] = useState(true);
  const [cityOptionsError, setCityOptionsError] = useState("");
  const [selectedArea, setSelectedArea] = useState("");
  const [apiKey, setApiKey] = useState(loadApiKeyFromSession);
  const [submissionForm, setSubmissionForm] = useState({
    submissionType: "PINT",
    city: DEFAULT_CITY,
    area: "",
    amount: "",
    evidenceNote: ""
  });
  const [submissionValidationErrors, setSubmissionValidationErrors] = useState({});
  const [submissionLoading, setSubmissionLoading] = useState(false);
  const [submissionError, setSubmissionError] = useState("");
  const [submissionSuccess, setSubmissionSuccess] = useState(null);

  const [health, setHealth] = useState(null);
  const [healthLoading, setHealthLoading] = useState(true);
  const [healthError, setHealthError] = useState("");

  const [cityData, setCityData] = useState(null);
  const [cityDataLoading, setCityDataLoading] = useState(true);
  const [cityDataError, setCityDataError] = useState("");

  useEffect(() => {
    let cancelled = false;

    async function loadCityOptions() {
      setCityOptionsLoading(true);
      setCityOptionsError("");
      try {
        const payload = await apiClient.getRentCities({ minSampleSize: CITY_DISCOVERY_MIN_SAMPLE_SIZE });
        const nextOptions = (payload.cities || []).map((item) => item.name).filter(Boolean);
        const resolvedOptions = nextOptions.length > 0 ? nextOptions : FALLBACK_CITY_OPTIONS;

        if (!cancelled) {
          setCityOptions(resolvedOptions);
          setCity((previous) => (resolvedOptions.includes(previous) ? previous : resolvedOptions[0]));
        }
      } catch (error) {
        if (!cancelled) {
          setCityOptions(FALLBACK_CITY_OPTIONS);
          setCityOptionsError(error instanceof Error ? error.message : "Failed to load city options.");
        }
      } finally {
        if (!cancelled) {
          setCityOptionsLoading(false);
        }
      }
    }

    loadCityOptions();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function loadHealth() {
      setHealthLoading(true);
      setHealthError("");
      try {
        const payload = await apiClient.getHealth();
        if (!cancelled) {
          setHealth(payload);
        }
      } catch (error) {
        if (!cancelled) {
          setHealthError(error instanceof Error ? error.message : "Failed to load health status.");
        }
      } finally {
        if (!cancelled) {
          setHealthLoading(false);
        }
      }
    }

    loadHealth();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function loadCityData() {
      setCityDataLoading(true);
      setCityDataError("");
      try {
        const [rent, cityAffordability, areaAffordability] = await Promise.all([
          apiClient.getCityRentAnalytics(city),
          apiClient.getAffordabilityScore(city, { components: AFFORDABILITY_COMPONENTS }),
          apiClient.getCityAreasAffordability(city, { components: AFFORDABILITY_COMPONENTS })
        ]);

        const rankedAreas = [...(areaAffordability.areas || [])].sort((a, b) => b.score - a.score);

        if (!cancelled) {
          setCityData({
            rent,
            cityAffordability,
            areaAffordability: {
              ...areaAffordability,
              areas: rankedAreas
            }
          });
          setSelectedArea((previous) => {
            if (previous && rankedAreas.some((item) => item.area === previous)) {
              return previous;
            }
            return rankedAreas[0]?.area || "";
          });
        }
      } catch (error) {
        if (!cancelled) {
          setCityData(null);
          setSelectedArea("");
          setCityDataError(error instanceof Error ? error.message : "Failed to load city dashboard.");
        }
      } finally {
        if (!cancelled) {
          setCityDataLoading(false);
        }
      }
    }

    loadCityData();
    return () => {
      cancelled = true;
    };
  }, [city]);

  useEffect(() => {
    try {
      if (apiKey.trim()) {
        sessionStorage.setItem(API_KEY_SESSION_STORAGE_KEY, apiKey.trim());
      } else {
        sessionStorage.removeItem(API_KEY_SESSION_STORAGE_KEY);
      }
    } catch {
      // Ignore storage availability failures.
    }
  }, [apiKey]);

  const selectedAreaData = cityData?.areaAffordability?.areas.find((item) => item.area === selectedArea) || null;
  const citySelectOptions = cityOptions.includes(city) ? cityOptions : [city, ...cityOptions];
  const areaSuggestions = cityData?.areaAffordability?.areas.map((item) => item.area) || [];

  function updateSubmissionField(field, value) {
    setSubmissionForm((previous) => ({ ...previous, [field]: value }));
    setSubmissionValidationErrors((previous) => {
      const next = { ...previous };
      delete next[field];
      return next;
    });
    setSubmissionError("");
    setSubmissionSuccess(null);
  }

  async function handleSubmissionCreate(event) {
    event.preventDefault();

    const validationErrors = validateSubmissionForm(submissionForm, apiKey);
    setSubmissionValidationErrors(validationErrors);
    setSubmissionError("");
    setSubmissionSuccess(null);

    if (Object.keys(validationErrors).length > 0) {
      return;
    }

    setSubmissionLoading(true);

    try {
      const payload = await apiClient.createSubmission(
        {
          city: submissionForm.city.trim(),
          area: submissionForm.area.trim() || null,
          submission_type: submissionForm.submissionType,
          amount_gbp: Number(submissionForm.amount.trim()).toFixed(2),
          submission_notes: submissionForm.evidenceNote.trim() || null
        },
        apiKey.trim()
      );

      setSubmissionSuccess(payload);
      setSubmissionForm((previous) => ({
        ...previous,
        amount: "",
        evidenceNote: ""
      }));
    } catch (error) {
      if (error instanceof ApiError) {
        let message = `Submission failed (${error.status}): ${error.message}`;
        if (error.status === 409) {
          message = `Duplicate detected (${error.status}): ${error.message}`;
        } else if (error.status === 401 || error.status === 403) {
          message = `Authentication error (${error.status}): ${error.message}`;
        } else if (error.status === 422) {
          message = `Validation failed (${error.status}): ${error.message}`;
        }
        setSubmissionError(message);
      } else {
        setSubmissionError(error instanceof Error ? error.message : "Failed to create submission.");
      }
    } finally {
      setSubmissionLoading(false);
    }
  }

  return (
    <main className="page">
      <section className="hero">
        <h1>Student Affordability Dashboard</h1>
      </section>

      <section className="panel">
        <h2>City Dashboard</h2>
        <div className="city-form">
          <label htmlFor="city-select">City</label>
          <select id="city-select" value={city} onChange={(event) => setCity(event.target.value)}>
            {citySelectOptions.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        </div>
        {cityOptionsLoading && <p className="status">Loading city options...</p>}
        {cityOptionsError && <p className="status error">City options fallback active: {cityOptionsError}</p>}

        {cityDataLoading && <p className="status">Loading dashboard data...</p>}
        {cityDataError && <p className="status error">Error: {cityDataError}</p>}

        {!cityDataLoading && !cityDataError && cityData && (
          <div className="cards">
            <article className="card">
              <h3>Rent Metrics ({cityData.rent.city})</h3>
              <dl className="grid">
                <div>
                  <dt>Average</dt>
                  <dd>GBP {formatMetric(cityData.rent.metrics.average)}</dd>
                </div>
                <div>
                  <dt>Median</dt>
                  <dd>GBP {formatMetric(cityData.rent.metrics.median)}</dd>
                </div>
                <div>
                  <dt>Min</dt>
                  <dd>GBP {formatMetric(cityData.rent.metrics.min)}</dd>
                </div>
                <div>
                  <dt>Max</dt>
                  <dd>GBP {formatMetric(cityData.rent.metrics.max)}</dd>
                </div>
                <div>
                  <dt>Sample Size</dt>
                  <dd>{cityData.rent.metrics.sample_size}</dd>
                </div>
              </dl>
            </article>

            <article className="card">
              <h3>City Affordability ({cityData.cityAffordability.city})</h3>
              <dl className="grid">
                <div>
                  <dt>Score</dt>
                  <dd>{cityData.cityAffordability.score}</dd>
                </div>
                <div>
                  <dt>Band</dt>
                  <dd>{cityData.cityAffordability.score_band}</dd>
                </div>
                <div>
                  <dt>Components</dt>
                  <dd>{cityData.cityAffordability.selected_components.join(", ")}</dd>
                </div>
                <div>
                  <dt>Areas Ranked</dt>
                  <dd>{cityData.areaAffordability.total}</dd>
                </div>
              </dl>
            </article>
          </div>
        )}
      </section>

      <section className="panel">
        <h2>Area Affordability Ranking</h2>
        {cityDataLoading && <p className="status">Loading area ranking...</p>}
        {cityDataError && <p className="status error">Error: {cityDataError}</p>}

        {!cityDataLoading && !cityDataError && cityData && (
          <>
            <div className="city-form">
              <label htmlFor="area-select">Area</label>
              <select
                id="area-select"
                value={selectedArea}
                onChange={(event) => setSelectedArea(event.target.value)}
                disabled={cityData.areaAffordability.areas.length === 0}
              >
                {cityData.areaAffordability.areas.map((item) => (
                  <option key={item.area} value={item.area}>
                    {item.area}
                  </option>
                ))}
              </select>
            </div>

            {selectedAreaData && (
              <article className="card area-score-card">
                <h3>
                  {cityData.cityAffordability.city} - {selectedAreaData.area}
                </h3>
                <dl className="grid">
                  <div>
                    <dt>Score</dt>
                    <dd>{selectedAreaData.score}</dd>
                  </div>
                  <div>
                    <dt>Band</dt>
                    <dd>{selectedAreaData.score_band}</dd>
                  </div>
                </dl>
              </article>
            )}

            {cityData.areaAffordability.areas.length === 0 ? (
              <p className="status">No area affordability rows available.</p>
            ) : (
              <div className="rank-list">
                {cityData.areaAffordability.areas.map((item, index) => (
                  <article
                    key={item.area}
                    className={`rank-item ${item.area === selectedArea ? "selected" : ""}`}
                    onClick={() => setSelectedArea(item.area)}
                    role="button"
                    tabIndex={0}
                    onKeyDown={(event) => {
                      if (event.key === "Enter" || event.key === " ") {
                        setSelectedArea(item.area);
                      }
                    }}
                  >
                    <p className="rank-position">#{index + 1}</p>
                    <p className="rank-area">{item.area}</p>
                    <p className="rank-score">{item.score}</p>
                  </article>
                ))}
              </div>
            )}
          </>
        )}
      </section>

      <section className="panel">
        <h2>Submit a Cost Observation</h2>
        <p className="subtle">
          Demo uses <code>X-API-Key</code>. Key is stored only in session storage for the current browser session.
        </p>

        <form className="submission-form" onSubmit={handleSubmissionCreate}>
          <div className="field full-width">
            <label htmlFor="api-key-input">Contributor API Key</label>
            <div className="inline-actions">
              <input
                id="api-key-input"
                type="password"
                value={apiKey}
                onChange={(event) => {
                  setApiKey(event.target.value);
                  setSubmissionValidationErrors((previous) => ({ ...previous, apiKey: undefined }));
                  setSubmissionError("");
                  setSubmissionSuccess(null);
                }}
                placeholder="Paste contributor key"
                autoComplete="off"
              />
              <button
                type="button"
                className="ghost-button"
                onClick={() => {
                  setApiKey("");
                  setSubmissionValidationErrors((previous) => ({ ...previous, apiKey: undefined }));
                  setSubmissionError("");
                  setSubmissionSuccess(null);
                }}
              >
                Clear
              </button>
            </div>
            {submissionValidationErrors.apiKey && <p className="field-error">{submissionValidationErrors.apiKey}</p>}
          </div>

          <div className="form-grid">
            <div className="field">
              <label htmlFor="submission-type">Submission Type</label>
              <select
                id="submission-type"
                value={submissionForm.submissionType}
                onChange={(event) => updateSubmissionField("submissionType", event.target.value)}
              >
                <option value="PINT">PINT</option>
                <option value="TAKEAWAY">TAKEAWAY</option>
              </select>
              {submissionValidationErrors.submissionType && (
                <p className="field-error">{submissionValidationErrors.submissionType}</p>
              )}
            </div>

            <div className="field">
              <label htmlFor="submission-city">City</label>
              <input
                id="submission-city"
                list="submission-city-options"
                value={submissionForm.city}
                onChange={(event) => updateSubmissionField("city", event.target.value)}
                placeholder="Leeds"
              />
              <datalist id="submission-city-options">
                {cityOptions.map((option) => (
                  <option key={option} value={option} />
                ))}
              </datalist>
              {submissionValidationErrors.city && <p className="field-error">{submissionValidationErrors.city}</p>}
            </div>

            <div className="field">
              <label htmlFor="submission-area">Area</label>
              <input
                id="submission-area"
                list="submission-area-options"
                value={submissionForm.area}
                onChange={(event) => updateSubmissionField("area", event.target.value)}
                placeholder="Hyde Park"
              />
              <datalist id="submission-area-options">
                {areaSuggestions.map((option) => (
                  <option key={option} value={option} />
                ))}
              </datalist>
              {submissionValidationErrors.area && <p className="field-error">{submissionValidationErrors.area}</p>}
            </div>

            <div className="field">
              <label htmlFor="submission-amount">Amount (GBP)</label>
              <input
                id="submission-amount"
                type="number"
                step="0.01"
                min="0.01"
                inputMode="decimal"
                value={submissionForm.amount}
                onChange={(event) => updateSubmissionField("amount", event.target.value)}
                placeholder="5.60"
              />
              {submissionValidationErrors.amount && <p className="field-error">{submissionValidationErrors.amount}</p>}
            </div>
          </div>

          <div className="field full-width">
            <label htmlFor="evidence-note">Evidence Note</label>
            <textarea
              id="evidence-note"
              value={submissionForm.evidenceNote}
              onChange={(event) => updateSubmissionField("evidenceNote", event.target.value)}
              placeholder="Optional context, for example receipt details or day/time."
              rows={3}
            />
            {submissionValidationErrors.evidenceNote && (
              <p className="field-error">{submissionValidationErrors.evidenceNote}</p>
            )}
          </div>

          <div className="inline-actions">
            <button type="submit" disabled={submissionLoading}>
              {submissionLoading ? "Submitting..." : "Submit Observation"}
            </button>
            <button
              type="button"
              className="ghost-button"
              onClick={() =>
                setSubmissionForm((previous) => ({
                  ...previous,
                  submissionType: "PINT",
                  amount: "",
                  evidenceNote: ""
                }))
              }
              disabled={submissionLoading}
            >
              Reset Amount/Note
            </button>
          </div>
        </form>

        {submissionError && <p className="status error">{submissionError}</p>}
        {submissionSuccess && (
          <p className="status success">
            Submission created: ID {submissionSuccess.id}, status {submissionSuccess.moderation_status}.
          </p>
        )}
      </section>

      <section className="panel">
        <h2>System Status</h2>
        <p className="subtle">
          Coursework demo frontend for the Student Affordability Intelligence API.
        </p>
        <p className="subtle">
          Backend URL: <code>{API_BASE_URL}</code>
        </p>
        {healthLoading && <p className="status">Loading health status...</p>}
        {healthError && <p className="status error">Error: {healthError}</p>}
        {!healthLoading && !healthError && health && (
          <dl className="grid">
            <div>
              <dt>Status</dt>
              <dd>{health.status}</dd>
            </div>
            <div>
              <dt>Timestamp</dt>
              <dd>{health.timestamp}</dd>
            </div>
          </dl>
        )}
      </section>
    </main>
  );
}
