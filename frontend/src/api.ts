/*
import type { HealthStatus, Job } from "./types";


async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    ...options,
    headers: { "Content-Type": "application/json", ...options?.headers },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || "服务暂时不可用，请稍后重试");
  }
  return response.json() as Promise<T>;
}


export function createJob(url: string): Promise<Job> {
  return request<Job>("/api/jobs", { method: "POST", body: JSON.stringify({ url }) });
}


export function getJob(id: string): Promise<Job> {
  return request<Job>(`/api/jobs/${id}`);
}


export function retryJob(id: string): Promise<Job> {
  return request<Job>(`/api/jobs/${id}/retry`, { method: "POST" });
}


export function getHealth(): Promise<HealthStatus> {
  return request<HealthStatus>("/api/health");
}
*/

import type {
  AuthResponse,
  HealthStatus,
  Job,
  LedgerEntry,
  LoginPayload,
  PointsResponse,
  RegisterPayload,
  User,
} from "./types";

const tokenKey = "productlens_access_token";

export function getStoredToken(): string | null {
  return window.localStorage.getItem(tokenKey);
}

export function storeToken(token: string): void {
  window.localStorage.setItem(tokenKey, token);
}

export function clearToken(): void {
  window.localStorage.removeItem(tokenKey);
}

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const token = getStoredToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options?.headers as Record<string, string> | undefined),
  };
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }
  const response = await fetch(url, { ...options, headers });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || "Request failed");
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return response.json() as Promise<T>;
}

export async function register(payload: RegisterPayload): Promise<AuthResponse> {
  const response = await request<AuthResponse>("/api/auth/register", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  storeToken(response.access_token);
  return response;
}

export async function login(payload: LoginPayload): Promise<AuthResponse> {
  const response = await request<AuthResponse>("/api/auth/login", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  storeToken(response.access_token);
  return response;
}

export async function logout(): Promise<void> {
  try {
    await request<void>("/api/auth/logout", { method: "POST" });
  } finally {
    clearToken();
  }
}

export function getMe(): Promise<User> {
  return request<User>("/api/me");
}

export function getPoints(): Promise<PointsResponse> {
  return request<PointsResponse>("/api/points");
}

export function getPointLedger(): Promise<LedgerEntry[]> {
  return request<LedgerEntry[]>("/api/points/ledger");
}

export function createJob(url: string): Promise<Job> {
  return request<Job>("/api/jobs", { method: "POST", body: JSON.stringify({ url }) });
}

export function getJob(id: string): Promise<Job> {
  return request<Job>(`/api/jobs/${id}`);
}

export function retryJob(id: string): Promise<Job> {
  return request<Job>(`/api/jobs/${id}/retry`, { method: "POST" });
}

export function getHealth(): Promise<HealthStatus> {
  return request<HealthStatus>("/api/health");
}
