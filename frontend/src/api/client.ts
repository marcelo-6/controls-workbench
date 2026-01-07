import type { ApiResponse } from "./types";

export class ApiClient {
  async request<T>(path: string, init?: RequestInit): Promise<T> {
    const res = await fetch(path, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...(init?.headers || {})
      },
      credentials: "include"
    });

    if (!res.ok) {
      // Try to read APIResponse error
      try {
        const payload = (await res.json()) as ApiResponse<any>;
        const msg =
          payload?.error?.detail ||
          payload?.message ||
          `HTTP ${res.status} ${res.statusText}`;
        throw new Error(msg);
      } catch {
        throw new Error(`HTTP ${res.status} ${res.statusText}`);
      }
    }

    // Not all endpoints return JSON (downloads)
    const contentType = res.headers.get("content-type") || "";
    if (contentType.includes("application/json")) {
      const payload = (await res.json()) as ApiResponse<T>;
      if (payload.status !== "success") {
        throw new Error(payload.error?.detail || payload.message || "Request failed");
      }
      if (payload.data === undefined) {
        throw new Error("API returned no data");
      }
      return payload.data;
    }

    // fallback
    // @ts-expect-error - for non-json endpoints, caller should use fetch directly
    return (await res.text()) as T;
  }

  async login(password: string): Promise<void> {
    await this.request<{ ok: boolean }>("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ password })
    });
  }

  async me(): Promise<{ ok: boolean; username: string }> {
    return await this.request<{ ok: boolean; username: string }>("/api/auth/me");
  }

  async logout(): Promise<void> {
    await this.request<{ ok: boolean }>("/api/auth/logout", { method: "POST", body: JSON.stringify({}) });
  }

  async listTools() {
    return await this.request<{ tools: any[] }>("/api/tools");
  }

  async createUpload(projectZip: File, tagsJson?: File) {
    const fd = new FormData();
    fd.append("project_zip", projectZip);
    if (tagsJson) fd.append("tags_json", tagsJson);

    const res = await fetch("/api/uploads", {
      method: "POST",
      body: fd,
      credentials: "include"
    });

    if (!res.ok) throw new Error(`Upload failed: HTTP ${res.status}`);
    const payload = (await res.json()) as ApiResponse<any>;
    if (payload.status !== "success" || !payload.data) {
      throw new Error(payload.error?.detail || payload.message || "Upload failed");
    }
    return payload.data;
  }

  async createJob(toolId: string, uploadId: string, params: Record<string, any> = {}) {
    return await this.request<{ jobId: string }>("/api/jobs", {
      method: "POST",
      body: JSON.stringify({ toolId, uploadId, params })
    });
  }

  async getJob(jobId: string) {
    return await this.request<any>(`/api/jobs/${jobId}`);
  }

  async getEvents(jobId: string, tail = 500) {
    return await this.request<any>(`/api/jobs/${jobId}/events?tail=${tail}`);
  }

  async listArtifacts(jobId: string) {
    return await this.request<any>(`/api/jobs/${jobId}/artifacts`);
  }

  async recentRuns(limit = 20) {
    return await this.request<any>(`/api/runs/recent?limit=${limit}`);
  }

  async getGraph(jobId: string) {
    return await this.request<any>(`/api/tools/ignition/graph/${jobId}`);
  }

  async getReport(jobId: string) {
    return await this.request<any>(`/api/tools/ignition/report/${jobId}`);
  }

  async getSummary(jobId: string) {
    return await this.request<any>(`/api/tools/ignition/summary/${jobId}`);
  }

  async logLatest(name: "api" | "worker" = "api") {
    return await this.request<any>(`/api/logs/latest?name=${name}`);
  }

  async logTail(name: "api" | "worker" = "api", n = 5000) {
    return await this.request<any>(`/api/logs/tail?name=${name}&n=${n}`);
  }
}

export const api = new ApiClient();
