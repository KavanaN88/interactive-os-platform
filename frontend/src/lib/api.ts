import type { AlgoConfig, AlgoInfo, CompareResponse, ProcessPayload, SimResponse } from "../types";

const BASE = import.meta.env.VITE_API_URL ?? "/api/v1";

// The access token lives only in memory (never localStorage); the refresh token is an httpOnly cookie the page cannot read.
let accessToken: string | null = null;
let refreshHandler: (() => Promise<boolean>) | null = null;
export const setAccessToken = (t: string | null) => { accessToken = t; };
export const setRefreshHandler = (h: (() => Promise<boolean>) | null) => { refreshHandler = h; };
export const CLIENT_HEADER = { "X-OSLab-Client": "web" };

export async function request<T>(path: string, init?: RequestInit, retried = false): Promise<T> {
  let res: Response;
  try {
    res = await fetch(BASE + path, {
      ...init,
      headers: { "Content-Type": "application/json", ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}), ...(init?.headers as Record<string, string> | undefined) },
    });
  } catch {
    throw new Error("Cannot reach the backend. Is it running on port 8000?");
  }
  if (res.status === 401 && !retried && refreshHandler && !path.startsWith("/auth/") && (await refreshHandler())) return request<T>(path, init, true);
  if (!res.ok) {
    let msg = res.statusText;
    try {
      const j = await res.json();
      if (typeof j.detail === "string") msg = j.detail;
      else if (Array.isArray(j.detail))
        msg = j.detail.map((d: { loc: (string | number)[]; msg: string }) => `${d.loc.slice(1).join(".")}: ${d.msg}`).join("; ");
    } catch { /* keep statusText */ }
    throw new Error(msg);
  }
  return res.json() as Promise<T>;
}

export const get = <T,>(path: string) => request<T>(path);
export const post = <T,>(path: string, body?: unknown, extra?: RequestInit) => request<T>(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body), ...extra });
export const put = <T,>(path: string, body: unknown) => request<T>(path, { method: "PUT", body: JSON.stringify(body) });
export const patch = <T,>(path: string, body: unknown) => request<T>(path, { method: "PATCH", body: JSON.stringify(body) });
export const del = <T,>(path: string) => request<T>(path, { method: "DELETE" });

export const api = {
  algorithms: () => request<AlgoInfo[]>("/cpu/algorithms"),
  simulate: (body: { algorithm: string; processes: ProcessPayload[]; quantum: number | null; levels: (number | null)[] | null }) =>
    request<SimResponse>("/cpu/simulate", { method: "POST", body: JSON.stringify(body) }),
  compare: (body: { processes: ProcessPayload[]; configs: AlgoConfig[] }) =>
    request<CompareResponse>("/cpu/compare", { method: "POST", body: JSON.stringify(body) }),
};
