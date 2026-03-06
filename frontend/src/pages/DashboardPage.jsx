import { useEffect, useState } from "react";
import { API_BASE_URL } from "../config.js";
import { apiClient } from "../lib/apiClient.js";

const DEFAULT_CITY = "Leeds";
const FALLBACK_CITY_OPTIONS = [DEFAULT_CITY];
const AFFORDABILITY_COMPONENTS = "rent,pint,takeaway";

function formatMetric(value) {
  if (value === null || value === undefined) {
    return "N/A";
  }
  return Number(value).toFixed(2);
}

export function DashboardPage() {
  const [cityOptions, setCityOptions] = useState(FALLBACK_CITY_OPTIONS);
  const [city, setCity] = useState(DEFAULT_CITY);
  const [cityOptionsLoading, setCityOptionsLoading] = useState(true);
  const [cityOptionsError, setCityOptionsError] = useState("");
  const [selectedArea, setSelectedArea] = useState("");

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
        const payload = await apiClient.getRentCities();
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

  const selectedAreaData = cityData?.areaAffordability?.areas.find((item) => item.area === selectedArea) || null;
  const citySelectOptions = cityOptions.includes(city) ? cityOptions : [city, ...cityOptions];

  return (
    <main className="page">
      <section className="hero">
        <h1>Student Affordability Dashboard</h1>
        <p className="subtle">Coursework demo frontend for the Student Affordability Intelligence API.</p>
        <p className="subtle">
          Backend URL: <code>{API_BASE_URL}</code>
        </p>
      </section>

      <section className="panel">
        <h2>Service Health</h2>
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
    </main>
  );
}
