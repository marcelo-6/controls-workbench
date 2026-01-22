// src/components/ArtifactPreview.tsx
import React, { useEffect, useMemo, useState } from "react";
import { Box, Typography, CircularProgress } from "@mui/material";
import { api } from "../api/client";

type Props = {
  jobId: string;
  kind: string;       // e.g. "node:<id>:view.json"
  file: string;       // e.g. "view.json" | "thumbnail" | "code.py"
};

function isJsonFile(file: string) {
  return file.toLowerCase().endsWith(".json");
}

function isImageFile(file: string) {
  const f = file.toLowerCase();
  if (f === "thumbnail") return true;
  return f.endsWith(".png") || f.endsWith(".jpg") || f.endsWith(".jpeg") || f.endsWith(".webp") || f.endsWith(".gif");
}

export default function ArtifactPreview({ jobId, kind, file }: Props) {
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");
  const [json, setJson] = useState<any>(null);
  const [text, setText] = useState<string>("");

  const href = useMemo(() => api.artifactHref(jobId, kind), [jobId, kind]);

  useEffect(() => {
    let alive = true;

    async function run() {
      setErr("");
      setJson(null);
      setText("");

      // images are rendered directly via href
      if (isImageFile(file)) return;

      setLoading(true);
      try {
        if (isJsonFile(file)) {
          const res = await api.getArtifactJson(jobId, kind);
          if (!alive) return;
          setJson(res?.data ?? res);
        } else {
          // default: treat as text (code.py, query.sql, config.json-not-json? etc)
          const res = await api.getArtifactText(jobId, kind);
          if (!alive) return;
          setText(res);
        }
      } catch (e: any) {
        if (!alive) return;
        setErr(e.message || "Failed to load artifact");
      } finally {
        if (!alive) return;
        setLoading(false);
      }
    }

    run();
    return () => {
      alive = false;
    };
  }, [jobId, kind, file]);

  if (isImageFile(file)) {
    return (
      <Box sx={{ border: "1px solid", borderColor: "divider", borderRadius: 2, overflow: "hidden" }}>
        <Box component="img" src={href} alt={kind} sx={{ width: "100%", display: "block" }} />
      </Box>
    );
  }

  return (
    <Box
      sx={{
        border: "1px solid",
        borderColor: "divider",
        borderRadius: 2,
        p: 1,
        maxHeight: 360,
        overflow: "auto",
      }}
    >
      {loading ? (
        <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
          <CircularProgress size={16} />
          <Typography variant="body2" color="text.secondary">
            Loading…
          </Typography>
        </Box>
      ) : err ? (
        <Typography variant="body2" color="error">
          {err}
        </Typography>
      ) : json !== null ? (
        <Box sx={{ fontFamily: "ui-monospace, monospace", fontSize: 12, whiteSpace: "pre-wrap" }}>
          {JSON.stringify(json, null, 2)}
        </Box>
      ) : (
        <Box sx={{ fontFamily: "ui-monospace, monospace", fontSize: 12, whiteSpace: "pre" }}>{text}</Box>
      )}
    </Box>
  );
}
