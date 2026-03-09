import { useEffect, useMemo, useState } from "react";
import { ApiError, apiClient } from "./lib/apiClient.js";
import { DashboardPage } from "./pages/DashboardPage.jsx";
import { ModeratorPage } from "./pages/ModeratorPage.jsx";
import { AuthPage } from "./pages/AuthPage.jsx";
import brandLogo from "./assets/sai-logo.svg";

const AUTH_TOKEN_STORAGE_KEY = "sai_auth_token";

function loadStoredAuthToken() {
  try {
    return localStorage.getItem(AUTH_TOKEN_STORAGE_KEY) || "";
  } catch {
    return "";
  }
}

export default function App() {
  const [activePage, setActivePage] = useState("login");
  const [authToken, setAuthToken] = useState(loadStoredAuthToken);
  const [currentUser, setCurrentUser] = useState(null);
  const [authLoading, setAuthLoading] = useState(Boolean(loadStoredAuthToken()));
  const [authError, setAuthError] = useState("");

  useEffect(() => {
    try {
      if (authToken) {
        localStorage.setItem(AUTH_TOKEN_STORAGE_KEY, authToken);
      } else {
        localStorage.removeItem(AUTH_TOKEN_STORAGE_KEY);
      }
    } catch {
      // Ignore storage access failures.
    }
  }, [authToken]);

  useEffect(() => {
    let cancelled = false;

    async function resolveCurrentUser() {
      if (!authToken) {
        if (!cancelled) {
          setCurrentUser(null);
          setAuthLoading(false);
        }
        return;
      }

      setAuthLoading(true);
      setAuthError("");
      try {
        const profile = await apiClient.getCurrentUser(authToken);
        if (!cancelled) {
          setCurrentUser(profile);
          setActivePage((previous) => (previous === "login" || previous === "register" ? "dashboard" : previous));
        }
      } catch (requestError) {
        if (!cancelled) {
          setCurrentUser(null);
          setAuthToken("");
          setActivePage("login");
          if (requestError instanceof ApiError) {
            setAuthError(`Session invalid (${requestError.status}): ${requestError.message}`);
          } else if (requestError instanceof Error) {
            setAuthError(requestError.message);
          } else {
            setAuthError("Session invalid. Please log in again.");
          }
        }
      } finally {
        if (!cancelled) {
          setAuthLoading(false);
        }
      }
    }

    resolveCurrentUser();
    return () => {
      cancelled = true;
    };
  }, [authToken]);

  const isAuthenticated = Boolean(authToken && currentUser);
  const isModerator = (currentUser?.role || "").toUpperCase() === "MODERATOR";
  const welcomeName = useMemo(() => {
    if (!currentUser) {
      return "";
    }
    return currentUser.display_name || currentUser.email;
  }, [currentUser]);

  function handleLoginSuccess(token) {
    setAuthToken(token);
    setAuthError("");
  }

  function handleLogout() {
    setAuthToken("");
    setCurrentUser(null);
    setActivePage("login");
    setAuthError("");
  }

  const authMode = activePage === "register" ? "register" : "login";

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
            {isAuthenticated ? (
              <>
                <button
                  type="button"
                  className={`nav-button ${activePage === "dashboard" ? "active" : ""}`}
                  onClick={() => setActivePage("dashboard")}
                >
                  Dashboard
                </button>
                {isModerator && (
                  <button
                    type="button"
                    className={`nav-button ${activePage === "moderator" ? "active" : ""}`}
                    onClick={() => setActivePage("moderator")}
                  >
                    Moderator
                  </button>
                )}
                <span className="auth-chip" title={currentUser?.email || ""}>
                  {welcomeName}
                </span>
                <button type="button" className="nav-button ghost-nav-button" onClick={handleLogout}>
                  Log out
                </button>
              </>
            ) : (
              <>
                <button
                  type="button"
                  className={`nav-button ${authMode === "login" ? "active" : ""}`}
                  onClick={() => setActivePage("login")}
                >
                  Login
                </button>
                <button
                  type="button"
                  className={`nav-button ${authMode === "register" ? "active" : ""}`}
                  onClick={() => setActivePage("register")}
                >
                  Register
                </button>
              </>
            )}
          </nav>
        </div>
      </header>

      {authLoading && (
        <main className="page">
          <section className="panel">
            <h2>Loading session...</h2>
            <p className="subtle">Checking saved login details.</p>
          </section>
        </main>
      )}

      {!authLoading && !isAuthenticated && (
        <>
          {authError && (
            <main className="page">
              <section className="panel">
                <p className="status error">{authError}</p>
              </section>
            </main>
          )}
          <AuthPage
            mode={authMode}
            onLoginSuccess={handleLoginSuccess}
            onSwitchMode={() => setActivePage(authMode === "register" ? "login" : "register")}
          />
        </>
      )}

      {!authLoading && isAuthenticated && (
        <>
          {activePage === "dashboard" || !isModerator ? (
            <DashboardPage currentUser={currentUser} authToken={authToken} />
          ) : (
            <ModeratorPage currentUser={currentUser} authToken={authToken} />
          )}
        </>
      )}
    </>
  );
}
