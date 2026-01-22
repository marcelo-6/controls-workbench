import type { ApiResponse } from "./types";

/**
 * Represents a single artifact produced by a job run.
 */
export type RunArtifact = {
  /** Artifact category or type identifier */
  kind: string;

  /** Relative path to the artifact within the run's storage */
  relPath: string;

  /** MIME type of the artifact content */
  contentType: string;

  /** Size of the artifact in bytes */
  sizeBytes: number;

  /** Optional metadata associated with the artifact */
  meta?: any | null;
};

/**
 * High‑level API client for interacting with the backend service.
 * Handles authentication, job execution, artifact retrieval, and
 * standardized error handling for JSON API responses.
 */
export class ApiClient {
  /**
   * Performs a typed HTTP request to the backend API.
   *
   * - Automatically attaches JSON headers
   * - Includes credentials (cookies)
   * - Logs request/response timing for debugging
   * - Normalizes API error responses into thrown exceptions
   *
   * @template T Expected response data type
   * @param path API endpoint path (e.g. `/api/auth/me`)
   * @param init Optional fetch configuration
   * @returns Parsed response payload of type `T`
   * @throws Error when network fails, JSON parsing fails, or API returns non‑success status
   */
  async request<T>(path: string, init?: RequestInit): Promise<T> {
    const start = performance.now();
    console.debug(`%c[API] → ${path}`, "color: #0af; font-weight: bold", { init });

    let res: Response;
    try {
      res = await fetch(path, {
        ...init,
        headers: {
          "Content-Type": "application/json",
          ...(init?.headers || {}),
        },
        credentials: "include",
      });
    } catch (networkErr) {
      console.error(`%c[API] NETWORK ERROR ← ${path}`, "color: red; font-weight: bold", networkErr);
      throw networkErr;
    }

    console.debug(
      `%c[API] ← ${path} status=${res.status} (${(performance.now() - start).toFixed(1)}ms)`,
      "color: #0af; font-weight: bold",
      { headers: Object.fromEntries(res.headers.entries()) }
    );

    if (!res.ok) {
      console.warn(`%c[API] Non-OK response ← ${path}`, "color: orange; font-weight: bold");

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

    const contentType = res.headers.get("content-type") || "";
    if (contentType.includes("application/json")) {
      let payload: ApiResponse<T>;
      try {
        payload = (await res.json()) as ApiResponse<T>;
        console.debug("[API] JSON payload:", payload);
      } catch (jsonErr) {
        console.error(`%c[API] JSON PARSE ERROR ← ${path}`, "color: red; font-weight: bold", jsonErr);
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

    const text = await res.text();
    console.debug("[API] Text response:", text);
    return text as unknown as T;
  }

  /**
   * Authenticates the user using a password.
   *
   * @param password Application password
   */
  async login(password: string): Promise<void> {
    await this.request<{ ok: boolean }>("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ password }),
    });
  }

  /**
   * Retrieves information about the currently authenticated user.
   *
   * @returns Object containing username and auth status
   */
  async me(): Promise<{ ok: boolean; username: string }> {
    return await this.request<{ ok: boolean; username: string }>("/api/auth/me");
  }

  /**
   * Logs out the current user.
   */
  async logout(): Promise<void> {
    await this.request<{ ok: boolean }>("/api/auth/logout", {
      method: "POST",
      body: JSON.stringify({}),
    });
  }

  /**
   * Lists all available tools that can be executed.
   */
  async listTools() {
    return await this.request<{ tools: any[] }>("/api/tools");
  }

  /**
   * Uploads a project ZIP (and optional tags JSON) to create a new upload record.
   *
   * @param projectZip ZIP file containing project data
   * @param tagsJson Optional JSON file containing tag metadata
   * @returns Upload metadata returned by the server
   * @throws Error if upload fails or API returns an error
   */
  async createUpload(projectZip: File, tagsJson?: File) {
    const fd = new FormData();
    fd.append("project_zip", projectZip);
    if (tagsJson) fd.append("tags_json", tagsJson);

    const res = await fetch("/api/uploads", {
      method: "POST",
      body: fd,
      credentials: "include",
    });

    if (!res.ok) throw new Error(`Upload failed: HTTP ${res.status}`);

    const payload = (await res.json()) as ApiResponse<any>;
    if (payload.status !== "success" || !payload.data) {
      throw new Error(payload.error?.detail || payload.message || "Upload failed");
    }
    return payload.data;
  }

  /**
   * Creates a new job run for a given tool and upload.
   *
   * @param toolId Identifier of the tool to execute
   * @param uploadId Identifier of the uploaded project
   * @param params Optional execution parameters
   * @returns Object containing the new job ID
   */
  async createJob(toolId: string, uploadId: string, params: Record<string, any> = {}) {
    return await this.request<{ jobId: string }>("/api/runs", {
      method: "POST",
      body: JSON.stringify({ toolId, uploadId, params }),
    });
  }

  /**
   * Retrieves metadata and status for a specific job.
   *
   * @param jobId Job identifier
   */
  async getJob(jobId: string) {
    return await this.request<any>(`/api/runs/${jobId}`);
  }

  /**
   * Retrieves recent events/logs for a job.
   *
   * @param jobId Job identifier
   * @param tail Maximum number of events to return
   */
  async getEvents(jobId: string, tail = 500) {
    return await this.request<any>(`/api/runs/${jobId}/events?tail=${tail}`);
  }

  /**
   * Lists recent job runs.
   *
   * @param limit Maximum number of runs to return
   */
  async recentRuns(limit = 20) {
    return await this.request<any>(`/api/runs/recent?limit=${limit}`);
  }

  // ---------------- Artifact helpers (raw fetch) ----------------

  /**
   * Constructs a public URL for downloading or previewing an artifact.
   *
   * @param jobId Job identifier
   * @param kind Artifact type
   */
  artifactHref(jobId: string, kind: string) {
    return `/api/runs/${encodeURIComponent(jobId)}/artifacts/${encodeURIComponent(kind)}`;
  }

  /**
   * Ensures a fetch response is OK or throws an error with readable text.
   *
   * @param res Fetch response
   * @throws Error if response is not OK
   */
  private async fetchOrThrow(res: Response) {
    if (!res.ok) {
      const text = await res.text().catch(() => "");
      const msg = text || `${res.status} ${res.statusText}`;
      throw new Error(msg);
    }
    return res;
  }

  /**
   * Retrieves an artifact and parses it as JSON.
   */
  async getArtifactJson(jobId: string, kind: string) {
    const res = await fetch(this.artifactHref(jobId, kind), { credentials: "include" });
    await this.fetchOrThrow(res);
    return res.json();
  }

  /**
   * Retrieves an artifact and returns it as plain text.
   */
  async getArtifactText(jobId: string, kind: string) {
    const res = await fetch(this.artifactHref(jobId, kind), { credentials: "include" });
    await this.fetchOrThrow(res);
    return res.text();
  }

  /**
   * Retrieves an artifact as a binary Blob.
   */
  async getArtifactBlob(jobId: string, kind: string) {
    const res = await fetch(this.artifactHref(jobId, kind), { credentials: "include" });
    await this.fetchOrThrow(res);
    return res.blob();
  }

  /**
   * Lists all artifacts for a job, normalizing different possible API shapes.
   *
   * @param jobId Job identifier
   * @returns Array of artifacts
   * @throws Error if response shape is unexpected
   */
  async listArtifacts(jobId: string): Promise<RunArtifact[]> {
    const data = await this.request<any>(`/api/runs/${jobId}/artifacts`);

    if (Array.isArray(data)) return data as RunArtifact[];
    if (data?.artifacts && Array.isArray(data.artifacts)) return data.artifacts as RunArtifact[];

    console.warn("[API] Unexpected listArtifacts() payload:", data);
    throw new Error("Unexpected artifacts response shape");
  }

  /**
   * Retrieves the tail of a server log (API or worker).
   *
   * @param name Log source ("api" or "worker")
   * @param n Number of lines to return
   */
  async logTail(name: "api" | "worker" = "api", n = 5000) {
    return await this.request<any>(`/api/logs/tail?name=${name}&n=${n}`);
  }
}

export const api = new ApiClient();