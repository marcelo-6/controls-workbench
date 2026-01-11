import React, { useEffect, useRef, useState } from "react";
import {
  Box,
  Button,
  Card,
  CardContent,
  CircularProgress,
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
  Chip,
  ToggleButton,
  ToggleButtonGroup,
  MenuItem
} from "@mui/material";
import UploadFileIcon from "@mui/icons-material/UploadFile";
import PlayArrowIcon from "@mui/icons-material/PlayArrow";
import RefreshIcon from "@mui/icons-material/Refresh";
import CheckCircleIcon from "@mui/icons-material/CheckCircle";
import ErrorIcon from "@mui/icons-material/Error";
import HourglassTopIcon from "@mui/icons-material/HourglassTop";
import HourglassEmptyIcon from "@mui/icons-material/HourglassEmpty";
import HelpOutlineIcon from "@mui/icons-material/HelpOutline";

import { useSnackbar } from "notistack";

import { api } from "../api/client";
import GraphView from "../components/GraphView";
import ProjectExplorerTree from "../components/ProjectExplorerTree";
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

  const [tree, setTree] = useState<any | null>(null);
  const [treeLoading, setTreeLoading] = useState(false);
  const [treeError, setTreeError] = useState<string>("");

  const [selectedRootId, setSelectedRootId] = useState<string | null>(null);
  const [depth, setDepth] = useState<number>(2);
  const [direction, setDirection] = useState<"both" | "in" | "out">("both");
  const [subgraphLoading, setSubgraphLoading] = useState(false);

  // Avoid restarting polling effects when state updates (which can cancel in-flight loads).
  // We use refs to track whether we've already loaded optional artifacts.
  const treeLoadInFlightRef = useRef(false);
  const treeLoadedRef = useRef(false);
  const treeNotFoundRef = useRef(false);
  const reportLoadedRef = useRef(false);
  const summaryLoadedRef = useRef(false);
  const graphFallbackLoadedRef = useRef(false);
  const pollTimerRef = useRef<number | null>(null);
  const pollInFlightRef = useRef(false);
  const eventsFinalLoadedRef = useRef(false);

  // Reset per-run load flags when switching jobs.
  useEffect(() => {
    treeLoadInFlightRef.current = false;
    treeLoadedRef.current = false;
    treeNotFoundRef.current = false;
    reportLoadedRef.current = false;
    summaryLoadedRef.current = false;
    graphFallbackLoadedRef.current = false;
    eventsFinalLoadedRef.current = false;
  }, [selectedJobId]);

  const capitalize = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);


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

  // Poll active job (only restart when switching runs)
  useEffect(() => {
    if (!selectedJobId) return;

    let cancelled = false;
    setCurrentJobId(selectedJobId);

    const stopPolling = () => {
      if (pollTimerRef.current !== null) {
        clearInterval(pollTimerRef.current);
        pollTimerRef.current = null;
      }
    };

    const tick = async () => {
      try {
        const st = await api.getJob(selectedJobId);
        if (cancelled) return;
        setJob(st);

        const terminal = st.status === "success" || st.status === "failed";
        const done = !!st.artifactsReady && terminal;

        // Poll events while running; once more after terminal to catch last lines
        if (!terminal || !eventsFinalLoadedRef.current) {
          const ev = await api.getEvents(selectedJobId, 2000);
          if (!cancelled) setLines(ev.lines || []);
          if (terminal) eventsFinalLoadedRef.current = true;
        }
        if (!done) return;

        // Indexed tree (preferred)
        if (
          st.status === "success" &&
          !treeLoadedRef.current &&
          !treeLoadInFlightRef.current
        ) {
          treeLoadInFlightRef.current = true;
          setTreeLoading(true);
          try {
            const t = await api.getTree(selectedJobId);
            if (!cancelled) setTree(t.tree);
            treeLoadedRef.current = true;
          } catch (e: any) {
            const msg = e.message || "Failed to load tree";
            if (!cancelled) setTreeError(msg);
            if (String(msg).toLowerCase().includes("tree not found")) {
              treeNotFoundRef.current = true;
            }
          } finally {
            treeLoadInFlightRef.current = false;
            if (!cancelled) setTreeLoading(false);
          }
        }

        // Back-compat fallback: older runs won't have a tree index
        if (
          st.status === "success" &&
          treeNotFoundRef.current &&
          !graphFallbackLoadedRef.current
        ) {
          graphFallbackLoadedRef.current = true;
          try {
            const g = await api.getGraph(selectedJobId);
            if (!cancelled) setGraph(g.graph);
          } catch {
            // ignore
          }
        }

        // Report/summary are still useful even with indexed graph slicing
        if (!reportLoadedRef.current) {
          reportLoadedRef.current = true;
          try {
            const r = await api.getReport(selectedJobId);
            if (!cancelled) setReport(r.report);
          } catch {
            // ignore
          }
        }

        if (!summaryLoadedRef.current) {
          summaryLoadedRef.current = true;
          try {
            const s = await api.getSummary(selectedJobId);
            if (!cancelled) setSummary(s.markdown || "");
          } catch {
            // ignore
          }
        }

        // Stop polling after we’ve reached a stable done state
        const treeAttempted = treeLoadedRef.current || treeNotFoundRef.current;
        const fallbackOk = !treeNotFoundRef.current || graphFallbackLoadedRef.current;

        if (treeAttempted && fallbackOk) {
          stopPolling();
        }

      } catch {
        // ignore transient
      }
    };

    tick();
    pollTimerRef.current = window.setInterval(tick, 1500);
    return () => {
      cancelled = true;
      stopPolling();
    };
  }, [selectedJobId, setCurrentJobId, setLines]);

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
      setTree(null);
      setTreeError("");
      setSelectedRootId(null);
      await refreshRecent();
    } catch (e: any) {
      enqueueSnackbar(e.message || "Failed to start job", { variant: "error" });
    } finally {
      setBusy(false);
    }
  };

  const statusChip = (status?: JobStatus) => {
    if (!status) return null;

    const map = {
      success: {
        color: "success",
        icon: <CheckCircleIcon />,
      },
      failed: {
        color: "error",
        icon: <ErrorIcon />,
      },
      running: {
        color: "warning",
        icon: <HourglassTopIcon />,
      },
      queued: {
        color: "info",
        icon: <HourglassEmptyIcon />,
      },
    } as const;

    const cfg = map[status] ?? {
      color: "default",
      icon: <HelpOutlineIcon />,
    };

    return (
      <Chip
        size="small"
        label={capitalize(status)}
        color={cfg.color as any}
        icon={cfg.icon}
        sx={{
          fontWeight: 500,
          textTransform: "none",
          "& .MuiChip-icon": {
            fontSize: 18,
          },
        }}
      />
    );
  };



  const loadSubgraph = async (rootId: string) => {
    if (!selectedJobId) return;
    setSelectedRootId(rootId);
    setSubgraphLoading(true);
    try {
      const res = await api.getSubgraph(selectedJobId, {
        rootIds: [rootId],
        depth,
        direction,
        maxNodes: 1200
      });
      setGraph(res.graph);
      enqueueSnackbar(`Loaded ${res.graph?.meta?.stats?.nodes || ""} nodes`, { variant: "success" });
    } catch (e: any) {
      enqueueSnackbar(e.message || "Failed to load subgraph", { variant: "error" });
    } finally {
      setSubgraphLoading(false);
    }
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
              <Box sx={{ display: "flex", alignItems: "center", px: 1.5, py: 1, gap: 1}}>
                <Typography variant="subtitle2" sx={{ flex: 1 }}>
                  Recent runs
                </Typography>
                <Button size="small" startIcon={<RefreshIcon />} onClick={refreshRecent}>
                  Refresh
                </Button>
              </Box>
              <Divider />
              <Box sx={{ flex: 1, minHeight: 0, overflow: "auto" }}>
                <List dense disablePadding sx={{ minHeight: 0, maxHeight: 200 }}>
                  {recent.map((r) => (
                    <ListItemButton
                      key={r.jobId}
                      selected={selectedJobId === r.jobId}
                      onClick={() => {
                        setSelectedJobId(r.jobId);
                        setGraph(null);
                        setReport(null);
                        setSummary("");
                        setTree(null);
                        setTreeError("");
                        setSelectedRootId(null);
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
            <Box sx={{ flex: 1, minHeight: 0, display: "flex" }}>
              {!selectedJobId ? (
                <Box sx={{ p: 2 }}>
                  <Typography variant="body2" color="text.secondary">
                    Select a run or start a new job.
                  </Typography>
                </Box>
              ) : job && job.status === "success" && tree ? (
                <Box sx={{ flex: 1, minHeight: 0, display: "flex" }}>
                  {/* Explorer panel */}
                  <Box
                    sx={{
                      width: 360,
                      borderRight: "1px solid",
                      borderColor: "divider",
                      display: "flex",
                      flexDirection: "column",
                      minHeight: 0
                    }}
                  >
                    <Box sx={{ p: 1, display: "flex", flexDirection: "column", gap: 1 }}>
                      <Typography variant="subtitle2">Graph slice</Typography>
                      <TextField
                        select
                        size="small"
                        label="Depth"
                        value={depth}
                        onChange={(e) => setDepth(Number(e.target.value))}
                      >
                        {[0, 1, 2, 3, 4, 5].map((n) => (
                          <MenuItem key={n} value={n}>
                            {n}
                          </MenuItem>
                        ))}
                      </TextField>
                      <ToggleButtonGroup
                        size="small"
                        value={direction}
                        exclusive
                        onChange={(_e, v) => v && setDirection(v)}
                      >
                        <ToggleButton value="both">Both</ToggleButton>
                        <ToggleButton value="in">In</ToggleButton>
                        <ToggleButton value="out">Out</ToggleButton>
                      </ToggleButtonGroup>
                    </Box>
                    <Divider />
                    <Box sx={{ flex: 1, minHeight: 0 }}>
                      <ProjectExplorerTree key={selectedJobId || "tree"} tree={tree} selectedId={selectedRootId} onSelect={loadSubgraph} />
                    </Box>
                  </Box>

                  {/* Graph panel */}
                  <Box sx={{ flex: 1, minHeight: 0, position: "relative" }}>
                    {subgraphLoading && <LinearProgress />}
                    {graph ? (
                      <GraphView jobId={selectedJobId} graph={graph} report={report} summary={summary} />
                    ) : (
                      <Box sx={{ p: 2 }}>
                        <Typography variant="body2" color="text.secondary">
                          Pick an element from the project explorer to generate a graph slice.
                        </Typography>
                      </Box>
                    )}
                  </Box>
                </Box>
              ) : job && job.status === "success" && treeLoading ? (
                <Box sx={{ p: 2, display: "flex", alignItems: "center", gap: 2 }}>
                  <CircularProgress size={20} />
                  <Typography variant="body2" color="text.secondary">
                    Loading project explorer...
                  </Typography>
                </Box>
              ) : graph ? (
                // Back-compat: older runs show full graph.json
                <GraphView jobId={selectedJobId} graph={graph} report={report} summary={summary} />
              ) : (
                <Box sx={{ p: 2 }}>
                  <Typography variant="body2" color="text.secondary">
                    {job && job.status === "success" && treeError
                      ? `Explorer not available: ${treeError}`
                      : "Waiting for artifacts..."}
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
