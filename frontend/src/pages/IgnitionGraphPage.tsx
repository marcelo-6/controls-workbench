import React, { useEffect, useMemo, useState } from "react";
import {
  Box,
  Button,
  Card,
  CardContent,
  Divider,
  Grid,
  LinearProgress,
  Paper,
  Stack,
  TextField,
  Typography,
  List,
  ListItemButton,
  ListItemText,
  Chip
} from "@mui/material";
import UploadFileIcon from "@mui/icons-material/UploadFile";
import PlayArrowIcon from "@mui/icons-material/PlayArrow";
import RefreshIcon from "@mui/icons-material/Refresh";
import { useSnackbar } from "notistack";

import { api } from "../api/client";
import GraphView from "../components/GraphView";
import { useOutput } from "../state/output";

type JobStatus = "queued" | "running" | "success" | "failed";

export default function IgnitionGraphPage() {
  const { enqueueSnackbar } = useSnackbar();
  const { setCurrentJobId, setLines } = useOutput();

  const [projectZip, setProjectZip] = useState<File | null>(null);
  const [tagsJson, setTagsJson] = useState<File | null>(null);

  const [busy, setBusy] = useState(false);

  const [recent, setRecent] = useState<any[]>([]);
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);

  const [job, setJob] = useState<any | null>(null);
  const [graph, setGraph] = useState<any | null>(null);
  const [report, setReport] = useState<any | null>(null);
  const [summary, setSummary] = useState<string>("");

  const refreshRecent = async () => {
    try {
      const res = await api.recentRuns(30);
      setRecent(res.runs || []);
    } catch (e: any) {
      enqueueSnackbar(e.message || "Failed to load recent runs", { variant: "error" });
    }
  };

  useEffect(() => {
    refreshRecent();
  }, []);

  // Poll active job
  useEffect(() => {
    if (!selectedJobId) return;

    let cancelled = false;
    setCurrentJobId(selectedJobId);

    const tick = async () => {
      try {
        const st = await api.getJob(selectedJobId);
        if (cancelled) return;
        setJob(st);

        const ev = await api.getEvents(selectedJobId, 2000);
        if (!cancelled) setLines(ev.lines || []);

        if (st.artifactsReady && (st.status === "success" || st.status === "failed")) {
          // Fetch artifacts (graph/report/summary) if not loaded
          if (!graph && st.status === "success") {
            const g = await api.getGraph(selectedJobId);
            if (!cancelled) setGraph(g.graph);
          }
          if (!report) {
            const r = await api.getReport(selectedJobId);
            if (!cancelled) setReport(r.report);
          }
          if (!summary) {
            const s = await api.getSummary(selectedJobId);
            if (!cancelled) setSummary(s.markdown || "");
          }
        }
      } catch (e: any) {
        // ignore transient
      }
    };

    tick();
    const id = setInterval(tick, 1500);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [selectedJobId, graph, report, summary, setCurrentJobId, setLines]);

  const submit = async () => {
    if (!projectZip) return;
    setBusy(true);
    try {
      const up = await api.createUpload(projectZip, tagsJson || undefined);
      const job = await api.createJob("ignition.graph", up.uploadId, {});
      enqueueSnackbar("Job created", { variant: "success" });
      setSelectedJobId(job.jobId);
      setGraph(null);
      setReport(null);
      setSummary("");
      await refreshRecent();
    } catch (e: any) {
      enqueueSnackbar(e.message || "Failed to start job", { variant: "error" });
    } finally {
      setBusy(false);
    }
  };

  const statusChip = (status?: JobStatus) => {
    if (!status) return null;
    const color =
      status === "success" ? "success" : status === "failed" ? "error" : status === "running" ? "warning" : "default";
    return <Chip size="small" label={status} color={color as any} />;
  };

  return (
    <Box sx={{ height: "100%", p: 2, display: "flex", flexDirection: "column", gap: 2, minHeight: 0 }}>
      <Grid container spacing={2} sx={{ minHeight: 0, flex: 1 }}>
        <Grid item xs={12} md={3} sx={{ minHeight: 0 }}>
          <Stack spacing={2} sx={{ height: "100%", minHeight: 0 }}>
            <Card>
              <CardContent sx={{ display: "flex", flexDirection: "column", gap: 1.5 }}>
                <Typography variant="subtitle1">Run Ignition Graph</Typography>
                <Divider />
                <Button component="label" variant="outlined" startIcon={<UploadFileIcon />}>
                  Select project export zip
                  <input
                    type="file"
                    hidden
                    accept=".zip"
                    onChange={(e) => setProjectZip(e.target.files?.[0] || null)}
                  />
                </Button>
                <Typography variant="caption" color="text.secondary">
                  {projectZip ? projectZip.name : "No file selected"}
                </Typography>

                <Button component="label" variant="outlined">
                  Optional tags export (json)
                  <input
                    type="file"
                    hidden
                    accept=".json"
                    onChange={(e) => setTagsJson(e.target.files?.[0] || null)}
                  />
                </Button>
                <Typography variant="caption" color="text.secondary">
                  {tagsJson ? tagsJson.name : "—"}
                </Typography>

                <Button
                  variant="contained"
                  startIcon={<PlayArrowIcon />}
                  disabled={!projectZip || busy}
                  onClick={submit}
                >
                  {busy ? "Starting..." : "Start"}
                </Button>
              </CardContent>
            </Card>

            <Paper sx={{ flex: 1, minHeight: 0, display: "flex", flexDirection: "column" }}>
              <Box sx={{ display: "flex", alignItems: "center", px: 1.5, py: 1, gap: 1 }}>
                <Typography variant="subtitle2" sx={{ flex: 1 }}>
                  Recent runs
                </Typography>
                <Button size="small" startIcon={<RefreshIcon />} onClick={refreshRecent}>
                  Refresh
                </Button>
              </Box>
              <Divider />
              <Box sx={{ flex: 1, minHeight: 0, overflow: "auto" }}>
                <List dense disablePadding>
                  {recent.map((r) => (
                    <ListItemButton
                      key={r.jobId}
                      selected={selectedJobId === r.jobId}
                      onClick={() => {
                        setSelectedJobId(r.jobId);
                        setGraph(null);
                        setReport(null);
                        setSummary("");
                      }}
                    >
                      <ListItemText
                        primary={r.jobId}
                        secondary={`${r.toolId} • ${new Date(r.createdAt).toLocaleString()}`}
                      />
                    </ListItemButton>
                  ))}
                  {!recent.length && (
                    <Box sx={{ p: 2 }}>
                      <Typography variant="body2" color="text.secondary">
                        No runs yet.
                      </Typography>
                    </Box>
                  )}
                </List>
              </Box>
            </Paper>
          </Stack>
        </Grid>

        <Grid item xs={12} md={9} sx={{ minHeight: 0 }}>
          <Paper sx={{ height: "100%", display: "flex", flexDirection: "column", minHeight: 0 }}>
            <Box sx={{ p: 1.5, display: "flex", alignItems: "center", gap: 2 }}>
              <Typography variant="subtitle1" sx={{ flex: 1 }}>
                Graph workspace
              </Typography>
              {job && (
                <Stack direction="row" spacing={1} alignItems="center">
                  {statusChip(job.status)}
                  <Typography variant="caption" color="text.secondary">
                    {job.progressHint || ""}
                  </Typography>
                </Stack>
              )}
            </Box>
            {job && (job.status === "queued" || job.status === "running") && <LinearProgress />}
            <Divider />
            <Box sx={{ flex: 1, minHeight: 0 }}>
              {graph ? (
                <GraphView graph={graph} report={report} summary={summary} />
              ) : (
                <Box sx={{ p: 2 }}>
                  <Typography variant="body2" color="text.secondary">
                    {selectedJobId ? "Waiting for graph artifacts..." : "Select a run or start a new job."}
                  </Typography>
                </Box>
              )}
            </Box>
          </Paper>
        </Grid>
      </Grid>
    </Box>
  );
}
