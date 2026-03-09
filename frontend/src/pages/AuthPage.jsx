import { useState } from "react";
import { ApiError, apiClient } from "../lib/apiClient.js";

function normalizeEmail(value) {
  return value.trim().toLowerCase();
}

function mapApiError(error, fallbackMessage) {
  if (error instanceof ApiError) {
    return `Request failed (${error.status}): ${error.message}`;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return fallbackMessage;
}

export function AuthPage({ mode, onLoginSuccess, onSwitchMode }) {
  const isRegister = mode === "register";
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [successMessage, setSuccessMessage] = useState("");
  const [form, setForm] = useState({
    displayName: "",
    email: "",
    password: ""
  });

  function updateField(field, value) {
    setForm((previous) => ({ ...previous, [field]: value }));
    setError("");
    setSuccessMessage("");
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setLoading(true);
    setError("");
    setSuccessMessage("");

    const email = normalizeEmail(form.email);
    const password = form.password;
    const displayName = form.displayName.trim();

    try {
      if (isRegister) {
        await apiClient.register({
          email,
          password,
          display_name: displayName
        });
        setSuccessMessage("Account created. You can now log in.");
        setForm((previous) => ({
          ...previous,
          password: ""
        }));
      } else {
        const payload = await apiClient.login({ email, password });
        onLoginSuccess(payload.access_token);
        setForm((previous) => ({
          ...previous,
          password: ""
        }));
      }
    } catch (requestError) {
      setError(mapApiError(requestError, "Authentication request failed."));
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="page">
      <section className="hero">
        <h1>{isRegister ? "Create Account" : "Log In"}</h1>
        <p className="subtle">
          Use account login for normal coursework website usage. API keys remain optional for developer-only flows.
        </p>
      </section>

      <section className="panel auth-panel">
        <h2>{isRegister ? "Register" : "Login"}</h2>
        <form className="submission-form" onSubmit={handleSubmit}>
          {isRegister && (
            <div className="field full-width">
              <label htmlFor="register-display-name">Display Name</label>
              <input
                id="register-display-name"
                value={form.displayName}
                onChange={(event) => updateField("displayName", event.target.value)}
                placeholder="Student User"
                autoComplete="name"
                required
              />
            </div>
          )}

          <div className="field full-width">
            <label htmlFor="auth-email">Email</label>
            <input
              id="auth-email"
              type="email"
              value={form.email}
              onChange={(event) => updateField("email", event.target.value)}
              placeholder="student@example.com"
              autoComplete="email"
              required
            />
          </div>

          <div className="field full-width">
            <label htmlFor="auth-password">Password</label>
            <input
              id="auth-password"
              type="password"
              value={form.password}
              onChange={(event) => updateField("password", event.target.value)}
              placeholder="SecurePass123"
              autoComplete={isRegister ? "new-password" : "current-password"}
              required
            />
          </div>

          <div className="inline-actions">
            <button type="submit" disabled={loading}>
              {loading ? "Submitting..." : isRegister ? "Create Account" : "Log In"}
            </button>
            <button type="button" className="ghost-button" onClick={onSwitchMode} disabled={loading}>
              {isRegister ? "Have an account? Log in" : "Need an account? Register"}
            </button>
          </div>
        </form>

        {error && <p className="status error">{error}</p>}
        {successMessage && <p className="status success">{successMessage}</p>}
      </section>
    </main>
  );
}
