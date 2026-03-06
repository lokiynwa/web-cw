import { useEffect, useState } from "react";
import { API_BASE_URL } from "../config.js";
import { apiClient } from "../lib/apiClient.js";

const DEFAULT_CITY = "Leeds";

function formatMetric(value) {
  if (value === null || value === undefined) {
    return "N/A";
  }
  return Number(value).toFixed(2);
}

export function DashboardPage() {
  const [cityInput, setCityInput] = useState(DEFAULT_CITY);
  const [city, setCity] = useState(DEFAULT_CITY);

  const [health, setHealth] = useState(null);
  const [healthLoading, setHealthLoading] = useState(true);
  const [healthError, setHealthError] = useState("");

  const [dashboard, setDashboard] = useState(null);
  const [dashboardLoading, setDashboardLoading] = useState(true);
  const [dashboardError, setDashboardError] = useState("");

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

    async function loadDashboard() {
      setDashboardLoading(true);
      setDashboardError("");
      try {
        const [rent, affordability] = await Promise.all([
          apiClient.getCityRentAnalytics(city),
          apiClient.getAffordabilityScore(city, { components: "rent" })
        ]);
        if (!cancelled) {
          setDashboard({ rent, affordability });
        }
      } catch (error) {
        if (!cancelled) {
          setDashboard(null);
          setDashboardError(error instanceof Error ? error.message : "Failed to load city dashboard.");
        }
      } finally {
        if (!cancelled) {
          setDashboardLoading(false);
        }
      }
    }

    loadDashboard();
    return () => {
      cancelled = true;
    };
  }, [city]);

  function handleSubmit(event) {
    event.preventDefault();
    const nextCity = cityInput.trim();
    if (nextCity) {
      setCity(nextCity);
    }
  }

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
        <form className="city-form" onSubmit={handleSubmit}>
          <label htmlFor="city-input">City</label>
          <input
            id="city-input"
            value={cityInput}
            onChange={(event) => setCityInput(event.target.value)}
            placeholder="Leeds"
          />
          <button type="submit">Load</button>
        </form>

        {dashboardLoading && <p className="status">Loading dashboard data...</p>}
        {dashboardError && <p className="status error">Error: {dashboardError}</p>}

        {!dashboardLoading && !dashboardError && dashboard && (
          <div className="cards">
            <article className="card">
              <h3>Rent Metrics ({dashboard.rent.city})</h3>
              <dl className="grid">
                <div>
                  <dt>Average</dt>
                  <dd>GBP {formatMetric(dashboard.rent.metrics.average)}</dd>
                </div>
                <div>
                  <dt>Median</dt>
                  <dd>GBP {formatMetric(dashboard.rent.metrics.median)}</dd>
                </div>
                <div>
                  <dt>Min</dt>
                  <dd>GBP {formatMetric(dashboard.rent.metrics.min)}</dd>
                </div>
                <div>
                  <dt>Max</dt>
                  <dd>GBP {formatMetric(dashboard.rent.metrics.max)}</dd>
                </div>
                <div>
                  <dt>Sample Size</dt>
                  <dd>{dashboard.rent.metrics.sample_size}</dd>
                </div>
              </dl>
            </article>

            <article className="card">
              <h3>Affordability Score ({dashboard.affordability.city})</h3>
              <dl className="grid">
                <div>
                  <dt>Score</dt>
                  <dd>{dashboard.affordability.score}</dd>
                </div>
                <div>
                  <dt>Band</dt>
                  <dd>{dashboard.affordability.score_band}</dd>
                </div>
                <div>
                  <dt>Components</dt>
                  <dd>{dashboard.affordability.selected_components.join(", ")}</dd>
                </div>
              </dl>
            </article>
          </div>
        )}
      </section>
    </main>
  );
}
