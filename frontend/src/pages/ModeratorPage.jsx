import { useEffect, useMemo, useState } from "react";
import { ApiError, apiClient } from "../lib/apiClient.js";

const MODERATOR_KEY_SESSION_STORAGE_KEY = "demo_moderator_api_key";

function loadModeratorKeyFromSession() {
  try {
    return sessionStorage.getItem(MODERATOR_KEY_SESSION_STORAGE_KEY) || "";
  } catch {
    return "";
  }
}

function formatAmount(value) {
  if (value === null || value === undefined) {
    return "N/A";
  }
  return Number(value).toFixed(2);
}

function formatTimestamp(value) {
  if (!value) {
    return "N/A";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toLocaleString();
}

export function ModeratorPage() {
  const [moderatorKey, setModeratorKey] = useState(loadModeratorKeyFromSession);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [submissions, setSubmissions] = useState([]);
  const [filterMode, setFilterMode] = useState("pending_or_flagged");
  const [actionSubmissionId, setActionSubmissionId] = useState(null);
  const [actionNoteBySubmissionId, setActionNoteBySubmissionId] = useState({});
  const [latestModerationResult, setLatestModerationResult] = useState(null);

  useEffect(() => {
    try {
      if (moderatorKey.trim()) {
        sessionStorage.setItem(MODERATOR_KEY_SESSION_STORAGE_KEY, moderatorKey.trim());
      } else {
        sessionStorage.removeItem(MODERATOR_KEY_SESSION_STORAGE_KEY);
      }
    } catch {
      // Ignore storage availability failures.
    }
  }, [moderatorKey]);

  async function loadModeratorQueue() {
    const trimmedKey = moderatorKey.trim();
    if (!trimmedKey) {
      setSubmissions([]);
      setError("");
      return;
    }

    setLoading(true);
    setError("");

    try {
      const [pendingPayload, allPayload] = await Promise.all([
        apiClient.getModerationQueue(trimmedKey, "PENDING"),
        apiClient.getSubmissions()
      ]);

      const pendingItems = pendingPayload.items || [];
      const flaggedItems = (allPayload.items || []).filter((item) => item.is_suspicious);

      const byId = new Map();
      pendingItems.forEach((item) => byId.set(item.id, item));
      flaggedItems.forEach((item) => byId.set(item.id, item));

      const combined = Array.from(byId.values()).sort((a, b) => {
        const left = Date.parse(a.submitted_at || "") || 0;
        const right = Date.parse(b.submitted_at || "") || 0;
        return right - left;
      });
      setSubmissions(combined);
    } catch (requestError) {
      if (requestError instanceof ApiError) {
        if (requestError.status === 401 || requestError.status === 403) {
          setError(`Moderator authentication failed (${requestError.status}): ${requestError.message}`);
        } else {
          setError(`Failed to load moderation queue (${requestError.status}): ${requestError.message}`);
        }
      } else {
        setError(requestError instanceof Error ? requestError.message : "Failed to load moderation queue.");
      }
      setSubmissions([]);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (moderatorKey.trim()) {
      loadModeratorQueue();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!moderatorKey.trim()) {
      setSubmissions([]);
      setError("");
    }
  }, [moderatorKey]);

  const filteredSubmissions = useMemo(() => {
    return submissions.filter((item) => {
      if (filterMode === "pending") {
        return item.moderation_status === "PENDING";
      }
      if (filterMode === "flagged") {
        return item.is_suspicious;
      }
      return item.moderation_status === "PENDING" || item.is_suspicious;
    });
  }, [filterMode, submissions]);

  async function handleModerationAction(submissionId, targetStatus) {
    const trimmedKey = moderatorKey.trim();
    if (!trimmedKey) {
      setError("Moderator API key is required.");
      return;
    }

    const noteValue = actionNoteBySubmissionId[submissionId]?.trim();
    const autoNote = targetStatus === "PENDING" ? "Flagged in moderator UI." : "";
    const moderatorNote = noteValue || autoNote || null;

    setActionSubmissionId(submissionId);
    setError("");

    try {
      const result = await apiClient.moderateSubmission(submissionId, targetStatus, moderatorNote, trimmedKey);
      setLatestModerationResult(result);
      await loadModeratorQueue();
    } catch (requestError) {
      if (requestError instanceof ApiError) {
        if (requestError.status === 401 || requestError.status === 403) {
          setError(`Moderator authentication failed (${requestError.status}): ${requestError.message}`);
        } else {
          setError(`Moderation action failed (${requestError.status}): ${requestError.message}`);
        }
      } else {
        setError(requestError instanceof Error ? requestError.message : "Moderation action failed.");
      }
    } finally {
      setActionSubmissionId(null);
    }
  }

  return (
    <main className="page">
      <section className="panel">
        <h1>Moderator Page</h1>
        <p className="subtle">
          Enter a moderator API key for queue access and moderation actions. Key is stored in session storage only.
        </p>

        <div className="field full-width">
          <label htmlFor="moderator-api-key">Moderator API Key</label>
          <div className="inline-actions">
            <input
              id="moderator-api-key"
              type="password"
              value={moderatorKey}
              onChange={(event) => {
                setModeratorKey(event.target.value);
                setError("");
              }}
              placeholder="Paste moderator key"
              autoComplete="off"
            />
            <button
              type="button"
              className="action-button"
              onClick={() => loadModeratorQueue()}
              disabled={loading || !moderatorKey.trim()}
            >
              Refresh
            </button>
            <button
              type="button"
              className="ghost-button"
              onClick={() => {
                setModeratorKey("");
                setSubmissions([]);
                setLatestModerationResult(null);
                setError("");
              }}
            >
              Clear
            </button>
          </div>
        </div>
      </section>

      <section className="panel">
        <h2>Pending / Flagged Submissions</h2>
        <div className="inline-actions">
          <label htmlFor="moderation-filter">View</label>
          <select id="moderation-filter" value={filterMode} onChange={(event) => setFilterMode(event.target.value)}>
            <option value="pending_or_flagged">Pending or flagged</option>
            <option value="pending">Pending only</option>
            <option value="flagged">Flagged only</option>
          </select>
        </div>

        {!moderatorKey.trim() && <p className="status">Enter a moderator key to load the moderation queue.</p>}
        {loading && <p className="status">Loading moderation queue...</p>}
        {error && <p className="status error">{error}</p>}

        {!loading && !error && moderatorKey.trim() && (
          <>
            <p className="subtle">
              Showing {filteredSubmissions.length} item(s) from {submissions.length} pending/flagged submissions.
            </p>
            {filteredSubmissions.length === 0 ? (
              <p className="status">No submissions match the selected moderation view.</p>
            ) : (
              <div className="moderation-list">
                {filteredSubmissions.map((item) => (
                  <article className="moderation-item" key={item.id}>
                    <div className="moderation-item-head">
                      <h3>
                        #{item.id} {item.submission_type} - GBP {formatAmount(item.amount_gbp)}
                      </h3>
                      <p className="subtle">
                        {item.city}
                        {item.area ? ` / ${item.area}` : ""}
                      </p>
                    </div>
                    <dl className="grid">
                      <div>
                        <dt>Status</dt>
                        <dd>{item.moderation_status}</dd>
                      </div>
                      <div>
                        <dt>Suspicious</dt>
                        <dd>{item.is_suspicious ? "Yes" : "No"}</dd>
                      </div>
                      <div>
                        <dt>Submitted</dt>
                        <dd>{formatTimestamp(item.submitted_at)}</dd>
                      </div>
                      <div>
                        <dt>Reasons</dt>
                        <dd>{item.suspicious_reasons?.length ? item.suspicious_reasons.join(", ") : "N/A"}</dd>
                      </div>
                    </dl>

                    <div className="field full-width">
                      <label htmlFor={`moderator-note-${item.id}`}>Moderator Note (optional)</label>
                      <input
                        id={`moderator-note-${item.id}`}
                        value={actionNoteBySubmissionId[item.id] || ""}
                        onChange={(event) =>
                          setActionNoteBySubmissionId((previous) => ({
                            ...previous,
                            [item.id]: event.target.value
                          }))
                        }
                        placeholder="Add moderation note"
                      />
                    </div>

                    <div className="inline-actions">
                      <button
                        type="button"
                        className="action-button"
                        onClick={() => handleModerationAction(item.id, "APPROVED")}
                        disabled={actionSubmissionId === item.id}
                      >
                        Approve
                      </button>
                      <button
                        type="button"
                        className="action-button danger-button"
                        onClick={() => handleModerationAction(item.id, "REJECTED")}
                        disabled={actionSubmissionId === item.id}
                      >
                        Reject
                      </button>
                      <button
                        type="button"
                        className="action-button ghost-button"
                        onClick={() => handleModerationAction(item.id, "PENDING")}
                        disabled={actionSubmissionId === item.id}
                      >
                        Flag
                      </button>
                    </div>
                  </article>
                ))}
              </div>
            )}
          </>
        )}
      </section>

      <section className="panel">
        <h2>Latest Moderation Result</h2>
        {!latestModerationResult ? (
          <p className="status">No moderation action taken in this session yet.</p>
        ) : (
          <dl className="grid">
            <div>
              <dt>Submission ID</dt>
              <dd>{latestModerationResult.submission_id}</dd>
            </div>
            <div>
              <dt>From</dt>
              <dd>{latestModerationResult.from_moderation_status || "N/A"}</dd>
            </div>
            <div>
              <dt>To</dt>
              <dd>{latestModerationResult.to_moderation_status}</dd>
            </div>
            <div>
              <dt>Moderator</dt>
              <dd>{latestModerationResult.moderator_key_name || "N/A"}</dd>
            </div>
            <div>
              <dt>Note</dt>
              <dd>{latestModerationResult.moderator_note || "N/A"}</dd>
            </div>
            <div>
              <dt>At</dt>
              <dd>{formatTimestamp(latestModerationResult.created_at)}</dd>
            </div>
          </dl>
        )}
      </section>
    </main>
  );
}
