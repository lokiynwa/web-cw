const defaultApiBaseUrl = "/api/v1";

function normalizeBaseUrl(rawUrl) {
  return (rawUrl || defaultApiBaseUrl).trim().replace(/\/+$/, "");
}

export const API_BASE_URL = normalizeBaseUrl(import.meta.env.VITE_API_BASE_URL);
