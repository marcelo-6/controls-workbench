// src/hooks/useArtifactIndex.ts
import { useEffect, useMemo, useState } from "react";
import { api } from "../api/client";

export type ArtifactListItem = {
  kind: string;
  relPath: string;
  contentType: string;
  sizeBytes: number;
  meta?: any | null;
};

export type NodeArtifacts = {
  nodeId: string;
  bySuffix: Map<string, ArtifactListItem>;
};

function parseFromKind(kind: string): { nodeId: string; suffix: string } | null {
  // node:<uuid>:<suffix>
  if (!kind.startsWith("node:")) return null;
  const parts = kind.split(":");
  if (parts.length < 3) return null;
  return { nodeId: parts[1], suffix: parts.slice(2).join(":") };
}

function parseFromRelPath(relPath: string): { nodeId: string; suffix: string } | null {
  // nodes/<uuid>/<filename>
  // examples:
  // nodes/<id>/resource.json  => suffix "resource.json"
  // nodes/<id>/thumbnail.png  => suffix "thumbnail" (normalize)
  // nodes/<id>/view.json      => suffix "view.json"
  const m = relPath.match(/^nodes\/([^/]+)\/([^/]+)$/);
  if (!m) return null;
  const nodeId = m[1];
  const filename = m[2];

  if (filename === "thumbnail.png") return { nodeId, suffix: "thumbnail" };
  return { nodeId, suffix: filename };
}

export function useArtifactIndex(jobId?: string | null) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>("");
  const [artifacts, setArtifacts] = useState<ArtifactListItem[]>([]);

  useEffect(() => {
    let alive = true;

    async function run() {
      if (!jobId) {
        setArtifacts([]);
        setError("");
        setLoading(false);
        return;
      }

      setLoading(true);
      setError("");

      try {
        // api.listArtifacts already returns payload.data (so { artifacts: [...] })
        const res = await api.listArtifacts(jobId);
        const list = (res as any)?.artifacts ?? [];
        if (!alive) return;
        setArtifacts(list);
      } catch (e: any) {
        if (!alive) return;
        setError(e.message || "Failed to list artifacts");
        setArtifacts([]);
      } finally {
        if (!alive) return;
        setLoading(false);
      }
    }

    run();
    return () => {
      alive = false;
    };
  }, [jobId]);

  const byNodeId = useMemo(() => {
    const m = new Map<string, NodeArtifacts>();

    const upsert = (nodeId: string, suffix: string, a: ArtifactListItem) => {
      if (!m.has(nodeId)) {
        m.set(nodeId, { nodeId, bySuffix: new Map() });
      }
      m.get(nodeId)!.bySuffix.set(suffix, a);
    };

    for (const a of artifacts) {
      const p1 = parseFromKind(a.kind);
      if (p1) upsert(p1.nodeId, p1.suffix, a);

      const p2 = parseFromRelPath(a.relPath);
      // relPath parse is a fallback/validator — don’t overwrite kind if it already exists
      if (p2 && !m.get(p2.nodeId)?.bySuffix.has(p2.suffix)) {
        upsert(p2.nodeId, p2.suffix, a);
      }
    }

    return m;
  }, [artifacts]);

  return { loading, error, artifacts, byNodeId };
}
