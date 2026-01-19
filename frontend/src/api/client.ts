import type { ApiResponse } from "./types";

export class ApiClient {
async request<T>(path: string, init?: RequestInit): Promise<T> {
  const start = performance.now();
  console.debug(
    `%c[API] → ${path}`,
    "color: #0af; font-weight: bold",
    { init }
  );

  let res: Response;
  try {
    res = await fetch(path, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...(init?.headers || {})
      },
      credentials: "include"
    });
  } catch (networkErr) {
    console.error(
      `%c[API] NETWORK ERROR ← ${path}`,
      "color: red; font-weight: bold",
      networkErr
    );
    throw networkErr;
  }

  console.debug(
    `%c[API] ← ${path} status=${res.status} (${(performance.now() - start).toFixed(1)}ms)`,
    "color: #0af; font-weight: bold",
    { headers: Object.fromEntries(res.headers.entries()) }
  );

  // Handle non-OK responses
  if (!res.ok) {
    console.warn(
      `%c[API] Non-OK response ← ${path}`,
      "color: orange; font-weight: bold"
    );

    try {
      const payload = (await res.json()) as ApiResponse<any>;
      console.warn("[API] Error payload:", payload);

      const msg =
        payload?.error?.detail ||
        payload?.message ||
        `HTTP ${res.status} ${res.statusText}`;

      throw new Error(msg);
    } catch (jsonErr) {
      console.error("[API] Failed to parse error JSON:", jsonErr);
      throw new Error(`HTTP ${res.status} ${res.statusText}`);
    }
  }

  // Detect JSON vs text
  const contentType = res.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    let payload: ApiResponse<T>;

    try {
      payload = (await res.json()) as ApiResponse<T>;
      console.debug("[API] JSON payload:", payload);
    } catch (jsonErr) {
      console.error(
        `%c[API] JSON PARSE ERROR ← ${path}`,
        "color: red; font-weight: bold",
        jsonErr
      );
      throw new Error("Failed to parse JSON response");
    }

    if (payload.status !== "success") {
      console.error("[API] API error payload:", payload);
      throw new Error(payload.error?.detail || payload.message || "Request failed");
    }

    if (payload.data === undefined) {
      console.error("[API] Missing data field:", payload);
      throw new Error("API returned no data");
    }

    return payload.data;
  }

  // Non-JSON fallback
  const text = await res.text();
  console.debug("[API] Text response:", text);
  return text as unknown as T;
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
    return await this.request<{ jobId: string }>("/api/runs", {
      method: "POST",
      body: JSON.stringify({ toolId, uploadId, params })
    });
  }

  async getJob(jobId: string) {
    return await this.request<any>(`/api/runs/${jobId}`);
  }

  async getEvents(jobId: string, tail = 500) {
    return await this.request<any>(`/api/runs/${jobId}/events?tail=${tail}`);
  }

  async listArtifacts(jobId: string) {
    return await this.request<any>(`/api/runs/${jobId}/artifacts`);
  }

  async recentRuns(limit = 20) {
    return await this.request<any>(`/api/runs/recent?limit=${limit}`);
  }

  async getGraph(jobId: string) {
    return await this.request<any>(`/api/runs/${jobId}/artifacts/graph`);
  }

  async getReport(jobId: string) {
    return await this.request<any>(`/api/runs/${jobId}/artifacts/report`);
  }

  async getSummary(jobId: string) {
    return await this.request<any>(`/api/runs/${jobId}/artifacts/summary`);
  }
  
  // ---------------- Artifact helpers (raw fetch) ----------------

  private artifactUrl(jobId: string, kind: string) {
    return `/api/runs/${encodeURIComponent(jobId)}/artifacts/${encodeURIComponent(kind)}`;
  }

  private async fetchOrThrow(res: Response) {
    if (!res.ok) {
      const text = await res.text().catch(() => "");
      const msg = text || `${res.status} ${res.statusText}`;
      throw new Error(msg);
    }
    return res;
  }

  async getArtifactJson(jobId: string, kind: string) {
    const res = await fetch(this.artifactUrl(jobId, kind), { credentials: "include" });
    await this.fetchOrThrow(res);
    return res.json();
  }

  async getArtifactText(jobId: string, kind: string) {
    const res = await fetch(this.artifactUrl(jobId, kind), { credentials: "include" });
    await this.fetchOrThrow(res);
    return res.text();
  }

  async getArtifactBlob(jobId: string, kind: string) {
    const res = await fetch(this.artifactUrl(jobId, kind), { credentials: "include" });
    await this.fetchOrThrow(res);
    return res.blob();
  }
  
  // ---------------- Ignition (indexed) ----------------

  async getTree(jobId: string) {
    return await this.request<any>(`/api/runs/${jobId}/artifacts/tree`);
  }

  async searchIndex(jobId: string, q: string) {
    const qs = new URLSearchParams({ q });
    return await this.request<any>(`/api/tools/ignition/search/${jobId}?${qs.toString()}`);
  }

  async getNodeDetails(jobId: string, nodeId: string) {
    return await this.request<any>(`/api/tools/ignition/node/${jobId}/${encodeURIComponent(nodeId)}`);
  }

  async getSubgraph(
    jobId: string,
    opts: {
      rootIds: string[];
      depth?: number;
      direction?: "in" | "out" | "both";
      maxNodes?: number;
    }
  ) {
    const qs = new URLSearchParams();
    for (const id of opts.rootIds) qs.append("root_ids", id);
    if (opts.depth !== undefined) qs.set("depth", String(opts.depth));
    if (opts.direction) qs.set("direction", opts.direction);
    if (opts.maxNodes !== undefined) qs.set("max_nodes", String(opts.maxNodes));
    return await this.request<any>(`/api/tools/ignition/subgraph/${jobId}?${qs.toString()}`);
  }

  async logLatest(name: "api" | "worker" = "api") {
    return await this.request<any>(`/api/logs/latest?name=${name}`);
  }

  async logTail(name: "api" | "worker" = "api", n = 5000) {
    return await this.request<any>(`/api/logs/tail?name=${name}&n=${n}`);
  }
}

export const api = new ApiClient();
