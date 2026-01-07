export type Status = "success" | "error";

export type ErrorField = { field: string; message: string };

export type ApiError = {
  code: string;
  detail: string;
  fields?: ErrorField[];
};

export type ApiMeta = {
  requestId?: string;
  timestampUtc?: string;
};

export type ApiResponse<T> = {
  status: Status;
  message?: string;
  data?: T;
  meta: ApiMeta;
  error?: ApiError | null;
};

export type ToolInfo = {
  toolId: string;
  name: string;
  category: string;
  version: string;
};

export type UploadCreated = {
  uploadId: string;
  receivedFiles: { name: string; sizeBytes: number }[];
};

export type JobCreated = { jobId: string };

export type JobState = {
  jobId: string;
  toolId: string;
  status: "queued" | "running" | "success" | "failed";
  createdAt: string;
  startedAt?: string | null;
  finishedAt?: string | null;
  progressHint?: string | null;
  artifactsReady: boolean;
};

export type LinesPayload = { lines: string[] };

export type ArtifactsList = {
  artifacts: { path: string; sizeBytes: number; url: string }[];
};

export type RecentRuns = {
  runs: {
    jobId: string;
    toolId: string;
    status: JobState["status"];
    createdAt: string;
    lastAccessedAt: string;
  }[];
};

export type GraphDoc = {
  meta: any;
  nodes: any[];
  edges: any[];
};

export type GraphPayload = { graph: GraphDoc };
export type ReportPayload = { report: any };
export type SummaryPayload = { markdown: string };
