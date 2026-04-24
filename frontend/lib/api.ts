import { clearAuth, getToken } from "./auth";
import type {
  BuildingDetail,
  DashboardResponse,
  LoginResponse,
  ScrapeTriggerResponse,
} from "./types";

const BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); }
}

async function request<T>(path: string, init: RequestInit = {}, timeoutMs?: number): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(init.headers as Record<string, string> | undefined),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const controller = timeoutMs ? new AbortController() : undefined;
  const timer = controller
    ? setTimeout(() => controller.abort(), timeoutMs)
    : undefined;

  let resp: Response;
  try {
    resp = await fetch(`${BASE}${path}`, {
      ...init,
      headers,
      signal: controller?.signal,
    });
  } finally {
    if (timer) clearTimeout(timer);
  }

  if (resp.status === 401) {
    // Token expired or invalid — clear and bounce to login.
    clearAuth();
    if (typeof window !== "undefined") window.location.href = "/login";
    throw new ApiError(401, "Session expired.");
  }

  if (!resp.ok) {
    const body = await resp.text().catch(() => "");
    let detail = body;
    try { detail = JSON.parse(body).detail || body; } catch {}
    throw new ApiError(resp.status, detail || `HTTP ${resp.status}`);
  }

  return resp.json() as Promise<T>;
}

export const api = {
  async login(email: string, password: string): Promise<LoginResponse> {
    return request("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
  },

  async dashboard(): Promise<DashboardResponse> {
    return request("/dashboard");
  },

  async building(id: number): Promise<BuildingDetail> {
    return request(`/buildings/${id}`);
  },

  async triggerScrape(): Promise<ScrapeTriggerResponse> {
    return request("/scrape/trigger", { method: "POST" }, 240_000);
  },

  async askChat(question: string): Promise<{ answer: string; error: string | null }> {
    return request("/chat/ask", {
      method: "POST",
      body: JSON.stringify({ question }),
    });
  },

  /** Per-building PDF blob URL. */
  async buildingPdfUrl(id: number): Promise<string> {
    const token = getToken();
    const resp = await fetch(`${BASE}/export/pdf/${id}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!resp.ok) throw new ApiError(resp.status, "Building PDF export failed");
    const blob = await resp.blob();
    return URL.createObjectURL(blob);
  },

  /** Download the PDF as a Blob — returns an object URL for anchor href. */
  async pdfUrl(): Promise<string> {
    const token = getToken();
    const resp = await fetch(`${BASE}/export/pdf`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!resp.ok) throw new ApiError(resp.status, "PDF export failed");
    const blob = await resp.blob();
    return URL.createObjectURL(blob);
  },
};

export { ApiError };
