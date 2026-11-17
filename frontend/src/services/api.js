const API_BASE_URL =
  import.meta.env?.VITE_API_BASE_URL ||
  "http://localhost:8000";


export function getFloodOverlayUrl(analysisId) {
  if (!analysisId) return null;

  return `${API_BASE_URL}/api/analysis/${encodeURIComponent(analysisId)}/flood-overlay`;
}

export function getChangeOverlayUrl(analysisId) {
  if (!analysisId) return null;

  return `${API_BASE_URL}/api/analysis/${encodeURIComponent(analysisId)}/change-overlay`;
}

async function parseResponse(response) {
  const contentType = response.headers.get("content-type") || "";

  if (contentType.includes("application/json")) {
    return response.json();
  }

  return response.text();
}

export async function request(endpoint, options = {}) {
  const response = await fetch(
    `${API_BASE_URL}${endpoint}`,
    {
      ...options,
      headers: {
        Accept: "application/json",
        ...(options.body instanceof FormData
          ? {}
          : {
              "Content-Type": "application/json",
            }),
        ...(options.headers || {}),
      },
    }
  );

  const data = await parseResponse(response);

  if (!response.ok) {
    const detail = typeof data === "object" && data?.detail;
    const message = typeof detail === "string"
      ? detail
      : Array.isArray(detail)
        ? detail.map((item) => item?.msg || JSON.stringify(item)).join("; ")
        : typeof data === "object" && data?.message
          ? data.message
          : `Request failed with status ${response.status}.`;

    throw new Error(message);
  }

  return data;
}

export async function getHealth() {
  return request("/api/health");
}

export async function uploadImage(file) {
  if (!file) {
    throw new Error("No image file provided.");
  }

  const formData = new FormData();
  formData.append("image", file);

  return request("/api/images/upload", {
    method: "POST",
    body: formData,
  });
}

export async function runAnalysis(payload) {
  return request("/api/analysis", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function sendQuery(payload) {
  return request("/api/query", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function getAnalysisResult(analysisId) {
  if (!analysisId) {
    throw new Error("Analysis ID is required.");
  }

  return request(
    `/api/analysis/${encodeURIComponent(analysisId)}`
  );
}

export async function getAnalysisHistory() {
  return request("/api/analysis/history");
}

export default {
  getHealth,
  uploadImage,
  runAnalysis,
  sendQuery,
  getAnalysisResult,
  getAnalysisHistory,
  getFloodOverlayUrl,
};
