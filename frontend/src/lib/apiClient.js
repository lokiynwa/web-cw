import { API_BASE_URL } from "../config.js";

export class ApiError extends Error {
  constructor(message, status, detail) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

async function request(path, options = {}) {
  const authHeaders = options.authToken
    ? {
        Authorization: `Bearer ${options.authToken}`
      }
    : {};

  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...authHeaders,
      ...(options.headers || {})
    },
    ...options
  });

  if (!response.ok) {
    let detail = null;
    try {
      const payload = await response.json();
      detail = payload?.detail ?? null;
    } catch {
      // Keep null detail when response is not JSON.
    }
    const message = formatErrorDetail(detail, response.status);
    throw new ApiError(message, response.status, detail);
  }

  return response.json();
}

function formatErrorDetail(detail, status) {
  if (typeof detail === "string" && detail.trim()) {
    return detail;
  }

  if (Array.isArray(detail) && detail.length > 0) {
    return detail
      .map((entry) => {
        const field = Array.isArray(entry?.loc) ? entry.loc.join(".") : "field";
        const message = entry?.msg || "Invalid value";
        return `${field}: ${message}`;
      })
      .join(" | ");
  }

  if (detail && typeof detail === "object") {
    if (typeof detail.message === "string" && Array.isArray(detail.reasons)) {
      return `${detail.message}: ${detail.reasons.join(", ")}`;
    }
    if (typeof detail.message === "string") {
      return detail.message;
    }
    return JSON.stringify(detail);
  }

  return `Request failed (${status})`;
}

function buildQuery(params) {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      query.set(key, String(value));
    }
  });
  return query.toString();
}

export const apiClient = {
  register(payload) {
    return request("/auth/register", {
      method: "POST",
      body: JSON.stringify(payload)
    });
  },

  login(payload) {
    return request("/auth/login", {
      method: "POST",
      body: JSON.stringify(payload)
    });
  },

  getCurrentUser(authToken) {
    return request("/auth/me", { authToken });
  },

  getHealth() {
    return request("/health");
  },

  getRentCities(options = {}) {
    const query = buildQuery({
      min_sample_size: options.minSampleSize
    });
    const suffix = query ? `?${query}` : "";
    return request(`/analytics/rent/cities${suffix}`);
  },

  getCityRentAnalytics(city, filters = {}) {
    const query = buildQuery({
      bedrooms: filters.bedrooms,
      property_type: filters.propertyType,
      ensuite_proxy: filters.ensuiteProxy
    });
    const suffix = query ? `?${query}` : "";
    return request(`/analytics/rent/cities/${encodeURIComponent(city)}${suffix}`);
  },

  getAffordabilityScore(city, options = {}) {
    const query = buildAffordabilityQuery(options);
    const suffix = query ? `?${query}` : "";
    return request(`/affordability/cities/${encodeURIComponent(city)}/score${suffix}`);
  },

  getCityAreasAffordability(city, options = {}) {
    const query = buildAffordabilityQuery(options);
    const suffix = query ? `?${query}` : "";
    return request(`/affordability/cities/${encodeURIComponent(city)}/areas${suffix}`);
  },

  createSubmission(payload, options = {}) {
    const headers = {};
    if (options.authToken) {
      headers.Authorization = `Bearer ${options.authToken}`;
    }
    if (options.apiKey) {
      headers["X-API-Key"] = options.apiKey;
    }

    return request("/submissions", {
      method: "POST",
      headers,
      body: JSON.stringify(payload)
    });
  },

  getSubmissions() {
    return request("/submissions");
  },

  getModerationQueue(apiKey, moderationStatus = "PENDING") {
    const query = buildQuery({ moderation_status: moderationStatus });
    const suffix = query ? `?${query}` : "";
    return request(`/moderation/submissions${suffix}`, {
      headers: {
        "X-API-Key": apiKey
      }
    });
  },

  moderateSubmission(submissionId, moderationStatus, moderatorNote, apiKey) {
    return request(`/submissions/${submissionId}/moderation`, {
      method: "POST",
      headers: {
        "X-API-Key": apiKey
      },
      body: JSON.stringify({
        moderation_status: moderationStatus,
        moderator_note: moderatorNote
      })
    });
  }
};

function buildAffordabilityQuery(options) {
  const query = buildQuery({
    components: options.components,
    rent_weight: options.rentWeight,
    pint_weight: options.pintWeight,
    takeaway_weight: options.takeawayWeight
  });
  return query;
}
