export const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";
export const WS_BASE = API_BASE.replace(/^http/, "ws");

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export async function api<T = any>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    ...options,
  });
  if (res.status === 204) return undefined as T;
  let data: any = null;
  try {
    data = await res.json();
  } catch {
    /* empty body */
  }
  if (!res.ok) {
    const detail = data?.detail;
    const message =
      typeof detail === "string" ? detail : detail && Array.isArray(detail) ? detail[0]?.msg || "请求失败" : data?.message || "请求失败";
    throw new ApiError(res.status, message);
  }
  return data as T;
}

export interface UserInfo {
  id: number;
  username: string;
  role: "user" | "admin";
  games_played: number;
  wins: number;
}

export async function getMe(): Promise<UserInfo | null> {
  try {
    const data = await api<{ user: UserInfo | null }>("/auth/me");
    return data.user;
  } catch {
    return null;
  }
}

export async function login(username: string, password: string) {
  return api("/auth/login", { method: "POST", body: JSON.stringify({ username, password }) });
}

export async function register(username: string, password: string) {
  return api("/auth/register", { method: "POST", body: JSON.stringify({ username, password }) });
}

export async function logout() {
  return api("/auth/logout", { method: "POST" });
}
