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
