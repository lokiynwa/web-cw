import { API_BASE_URL } from "../config.js";

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {})
    },
    ...options
  });

  if (!response.ok) {
    let detail = `Request failed (${response.status})`;
    try {
      const payload = await response.json();
      if (payload?.detail) {
        detail = typeof payload.detail === "string" ? payload.detail : JSON.stringify(payload.detail);
      }
    } catch {
      // Keep generic detail when response is not JSON.
    }
    throw new Error(detail);
  }

  return response.json();
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
  getHealth() {
    return request("/health");
  },

  getRentCities() {
    return request("/analytics/rent/cities");
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
