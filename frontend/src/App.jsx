import { useState } from "react";
import { DashboardPage } from "./pages/DashboardPage.jsx";
import { ModeratorPage } from "./pages/ModeratorPage.jsx";

export default function App() {
  const [activePage, setActivePage] = useState("dashboard");

  return (
    <>
      <header className="top-nav">
        <div className="top-nav-inner">
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
        </div>
      </header>
      {activePage === "dashboard" ? <DashboardPage /> : <ModeratorPage />}
    </>
  );
}
