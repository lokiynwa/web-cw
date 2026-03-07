import { useState } from "react";
import { DashboardPage } from "./pages/DashboardPage.jsx";
import { ModeratorPage } from "./pages/ModeratorPage.jsx";
import brandLogo from "./assets/sai-logo.svg";

export default function App() {
  const [activePage, setActivePage] = useState("dashboard");

  return (
    <>
      <header className="top-nav">
        <div className="top-nav-inner">
          <div className="brand">
            <img src={brandLogo} alt="Student Affordability Intelligence logo" className="brand-logo" />
            <div>
              <p className="brand-name">Student Affordability Intelligence</p>
              <p className="brand-subtitle">Coursework Demo</p>
            </div>
          </div>

          <nav className="top-nav-links" aria-label="Primary">
            <button
              type="button"
              className={`nav-button ${activePage === "dashboard" ? "active" : ""}`}
              onClick={() => setActivePage("dashboard")}
            >
              Dashboard
            </button>
            <button
              type="button"
              className={`nav-button ${activePage === "moderator" ? "active" : ""}`}
              onClick={() => setActivePage("moderator")}
            >
              Moderator
            </button>
          </nav>
        </div>
      </header>
      {activePage === "dashboard" ? <DashboardPage /> : <ModeratorPage />}
    </>
  );
}
