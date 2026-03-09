import { useEffect, useMemo, useState } from "react";
import { ApiError, apiClient } from "../lib/apiClient.js";

const STATUS_OPTIONS = ["ACTIVE", "FLAGGED", "REMOVED"];

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

function normalizeRole(role) {
  return (role || "").toUpperCase();
}

export function ModeratorPage({ currentUser, authToken }) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [submissions, setSubmissions] = useState([]);
  const [filterMode, setFilterMode] = useState("ACTIVE");
  const [actionSubmissionId, setActionSubmissionId] = useState(null);
  const [actionNoteBySubmissionId, setActionNoteBySubmissionId] = useState({});
  const [latestModerationResult, setLatestModerationResult] = useState(null);

  const isModerator = normalizeRole(currentUser?.role) === "MODERATOR";

  async function loadModeratorQueue() {
    if (!authToken) {
      setSubmissions([]);
      setError("Moderator login is required.");
      return;
    }

    setLoading(true);
    setError("");

    try {
      const payloads = await Promise.all(
        STATUS_OPTIONS.map((status) =>
          apiClient.getModerationQueue({
            moderationStatus: status,
            authToken
          })
        )
      );

      const combined = payloads.flatMap((payload) => payload.items || []).sort((a, b) => {
        const left = Date.parse(a.submitted_at || "") || 0;
        const right = Date.parse(b.submitted_at || "") || 0;
        return right - left;
      });

      setSubmissions(combined);
    } catch (requestError) {
      if (requestError instanceof ApiError) {
        if (requestError.status === 401 || requestError.status === 403) {
          setError(`Moderator authorization failed (${requestError.status}): ${requestError.message}`);
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
    if (isModerator && authToken) {
      loadModeratorQueue();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isModerator, authToken]);

  const filteredSubmissions = useMemo(
    () => submissions.filter((item) => item.moderation_status === filterMode),
    [filterMode, submissions]
  );

  async function handleModerationAction(submissionId, targetStatus) {
    if (!authToken) {
      setError("Moderator login is required.");
      return;
    }

    const noteValue = actionNoteBySubmissionId[submissionId]?.trim();
    const moderatorNote = noteValue || null;

    setActionSubmissionId(submissionId);
    setError("");

    try {
      const result = await apiClient.moderateSubmission(submissionId, targetStatus, moderatorNote, { authToken });
      setLatestModerationResult(result);
      await loadModeratorQueue();
    } catch (requestError) {
      if (requestError instanceof ApiError) {
        if (requestError.status === 401 || requestError.status === 403) {
          setError(`Moderator authorization failed (${requestError.status}): ${requestError.message}`);
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

  if (!isModerator) {
    return (
      <main className="page">
        <section className="panel">
          <h1>Moderator Page</h1>
          <p className="status error">Moderator role required. Your account does not have moderation access.</p>
        </section>
      </main>
    );
  }

  return (
    <main className="page">
      <section className="panel">
        <h1>Moderator Page</h1>
        <p className="subtle">Logged in as moderator: {currentUser?.display_name || currentUser?.email || "Unknown"}</p>
        <p className="subtle">
          Submissions are live immediately. Use this workflow to flag, remove, or restore entries after publication.
        </p>
        <div className="inline-actions">
          <button type="button" className="action-button" onClick={loadModeratorQueue} disabled={loading}>
            {loading ? "Refreshing..." : "Refresh Queue"}
          </button>
        </div>
      </section>

      <section className="panel">
        <h2>Review Submissions</h2>
        <div className="inline-actions">
          <label htmlFor="moderation-filter">View</label>
          <select id="moderation-filter" value={filterMode} onChange={(event) => setFilterMode(event.target.value)}>
            <option value="ACTIVE">Active</option>
            <option value="FLAGGED">Flagged</option>
            <option value="REMOVED">Removed</option>
          </select>
        </div>

        {loading && <p className="status">Loading moderation queue...</p>}
        {error && <p className="status error">{error}</p>}

        {!loading && !error && (
          <>
            <p className="subtle">
              Showing {filteredSubmissions.length} item(s) from {submissions.length} total reviewed submissions.
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
                      {item.moderation_status === "ACTIVE" && (
                        <>
                          <button
                            type="button"
                            className="action-button ghost-button"
                            onClick={() => handleModerationAction(item.id, "FLAGGED")}
                            disabled={actionSubmissionId === item.id}
                          >
                            Flag
                          </button>
                          <button
                            type="button"
                            className="action-button danger-button"
                            onClick={() => handleModerationAction(item.id, "REMOVED")}
                            disabled={actionSubmissionId === item.id}
                          >
                            Remove
                          </button>
                        </>
                      )}

                      {item.moderation_status === "FLAGGED" && (
                        <>
                          <button
                            type="button"
                            className="action-button"
                            onClick={() => handleModerationAction(item.id, "ACTIVE")}
                            disabled={actionSubmissionId === item.id}
                          >
                            Restore Active
                          </button>
                          <button
                            type="button"
                            className="action-button danger-button"
                            onClick={() => handleModerationAction(item.id, "REMOVED")}
                            disabled={actionSubmissionId === item.id}
                          >
                            Remove
                          </button>
                        </>
                      )}

                      {item.moderation_status === "REMOVED" && (
                        <button
                          type="button"
                          className="action-button"
                          onClick={() => handleModerationAction(item.id, "ACTIVE")}
                          disabled={actionSubmissionId === item.id}
                        >
                          Restore
                        </button>
                      )}
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
              <dd>{latestModerationResult.moderator_display_name || latestModerationResult.moderator_key_name || "N/A"}</dd>
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
