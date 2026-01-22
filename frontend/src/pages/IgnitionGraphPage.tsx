// @refresh reset
import React, { useEffect, useRef, useState } from "react";
import {
  Box,
  Button,
  Card,
  CardContent,
  CircularProgress,
  Divider,
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
  MenuItem,
  IconButton,
  Tooltip,
} from "@mui/material";
import { styled } from "@mui/material/styles";
import ContentCopyIcon from "@mui/icons-material/ContentCopy";
import UploadFileIcon from "@mui/icons-material/UploadFile";
import PlayArrowIcon from "@mui/icons-material/PlayArrow";
import RefreshIcon from "@mui/icons-material/Refresh";
import CheckCircleIcon from "@mui/icons-material/CheckCircle";
import ErrorIcon from "@mui/icons-material/Error";
import HourglassTopIcon from "@mui/icons-material/HourglassTop";
import HourglassEmptyIcon from "@mui/icons-material/HourglassEmpty";
import HelpOutlineIcon from "@mui/icons-material/HelpOutline";
import MenuIcon from "@mui/icons-material/Menu";
import ChevronLeftIcon from "@mui/icons-material/ChevronLeft";

import { useSnackbar } from "notistack";

import { api } from "../api/client";
import GraphView from "../components/GraphView";
import ProjectExplorerTree from "../components/ProjectExplorerTree";
import { useOutput } from "../state/output";

type JobStatus = "queued" | "running" | "success" | "failed";

const drawerWidth = 360;

const Sidebar = styled("div", {
  shouldForwardProp: (prop) => prop !== "open",
})<{ open: boolean }>(({ theme, open }) => ({
  width: open ? drawerWidth : 0,
  transition: theme.transitions.create("width", {
    easing: theme.transitions.easing.easeOut,
    duration: theme.transitions.duration.shortest,
  }),
  overflow: "hidden",
  flexShrink: 0,
  height: "100%",
}));

export default function IgnitionGraphPage() {
  const { enqueueSnackbar } = useSnackbar();
  const { setCurrentJobId, setLines } = useOutput();

  const [sidebarOpen, setSidebarOpen] = useState(true);

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

  const [treeAttempted, setTreeAttempted] = useState(false);
  const [graphAttempted, setGraphAttempted] = useState(false);

  // Avoid restarting polling effects when state updates (which can cancel in-flight loads).
  // We use refs to track whether we've already loaded optional artifacts.
  const treeLoadInFlightRef = useRef(false);
  const treeLoadedRef = useRef(false);
  const treeNotFoundRef = useRef(false);
  const reportLoadedRef = useRef(false);
  const summaryLoadedRef = useRef(false);
  const graphFallbackLoadedRef = useRef(false);
  const pollTimerRef = useRef<number | null>(null);
  const eventsFinalLoadedRef = useRef(false);
  const treeAttemptedRef = useRef(false);
  const graphAttemptedRef = useRef(false);


  useEffect(() => {
    console.log("IGNITION GRAPH PAGE MOUNTED");
    return () => console.log("IGNITION GRAPH PAGE UNMOUNTED");
  }, []);
  // Reset per-run load flags when switching jobs.
  useEffect(() => {
    treeLoadInFlightRef.current = false;
    treeLoadedRef.current = false;
    treeNotFoundRef.current = false;
    reportLoadedRef.current = false;
    summaryLoadedRef.current = false;
    graphFallbackLoadedRef.current = false;
    eventsFinalLoadedRef.current = false;
    treeAttemptedRef.current = false;
    graphAttemptedRef.current = false;

    setTreeAttempted(false);
    setGraphAttempted(false);
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

  const stopPolling = () => {
    if (pollTimerRef.current) {
      clearInterval(pollTimerRef.current);
      pollTimerRef.current = null;
    }
  };

  console.log("RENDER tree:", tree);
  console.log("RENDER graph:", graph);
  console.log("RENDER job:", job?.status);
  console.log("RENDER treeError:", treeError);

  useEffect(() => {
    refreshRecent();
  }, []);

  // Poll active job (only restart when switching runs)
  useEffect(() => {
    if (!selectedJobId) return;

    let cancelled = false;
    const ac = new AbortController();

    console.debug("%c[Polling started]", "color:#4caf50;font-weight:bold");

    const tick = async () => {
      if (cancelled) return;

      let st;
      try {
        st = await api.getJob(selectedJobId);
        if (!cancelled) setJob(st);
      } catch (e) {
        if (!cancelled) console.error("Failed to load job:", e);
        return;
      }

      const terminal = st.status === "success" || st.status === "failed";

      // Always poll events until terminal
      try {
        const ev = await api.getEvents(selectedJobId, 2000);
        if (!cancelled) setLines(ev.lines || []);
      } catch (e) {
        if (!cancelled) console.error("Failed to load events:", e);
      }

      if (!terminal) return;

      // TREE once
      if (!treeAttemptedRef.current) {
        treeAttemptedRef.current = true;
        setTreeAttempted(true);

        try {
          const t = await api.getArtifactJson(selectedJobId, "tree");
          console.debug("[TICK] tree:", t.data);
          if (!cancelled) setTree(t.data);
        } catch (e: any) {
          console.error("Tree load error:", e);
          if (!cancelled) setTreeError(e.message || "Failed to load tree");
        }
      }

      // GRAPH once
      if (!graphAttemptedRef.current) {
        graphAttemptedRef.current = true;
        setGraphAttempted(true);

        try {
          const g = await api.getArtifactJson(selectedJobId, "graph_full");
          console.debug("[TICK] graph:", g.data);
          if (!cancelled) setGraph(g.data);
        } catch (e) {
          console.error("Graph load error:", e);
        }
      }

      // Stop once both attempts are done
      if (treeAttemptedRef.current && graphAttemptedRef.current) {
        console.debug("%c[Polling stopped]", "color:#f44336;font-weight:bold");
        stopPolling();
      }
    };

    tick();
    pollTimerRef.current = window.setInterval(tick, 1500);

    return () => {
      cancelled = true;
      stopPolling();
      ac.abort();
    };
  }, [selectedJobId]);


  const submit = async () => {
    if (!projectZip) return;
    setBusy(true);
    try {
      const up = await api.createUpload(projectZip, tagsJson || undefined);
      const jobRes = await api.createJob("ignition.project.explorer", up.uploadId, {});
      enqueueSnackbar("Job created", { variant: "success" });

      setSelectedJobId(jobRes.jobId);
      // RESET ALL LOADER REFS
      treeLoadedRef.current = false;
      treeLoadInFlightRef.current = false;
      treeNotFoundRef.current = false;
      graphFallbackLoadedRef.current = false;
      eventsFinalLoadedRef.current = false;

      setSidebarOpen(false); // ✅ auto-collapse after starting

      setGraph(null);
      setReport(null);
      setSummary("");
      setTree(null);
      setTreeError("");
      setSelectedRootId(null);

      setTreeAttempted(false);
      setGraphAttempted(false);


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
      success: { color: "success", icon: <CheckCircleIcon /> },
      failed: { color: "error", icon: <ErrorIcon /> },
      running: { color: "warning", icon: <HourglassTopIcon /> },
      queued: { color: "info", icon: <HourglassEmptyIcon /> },
    } as const;

    const cfg = (map as any)[status] ?? { color: "default", icon: <HelpOutlineIcon /> };

    return (
      <Chip
        size="small"
        label={capitalize(status)}
        color={cfg.color}
        icon={cfg.icon}
        sx={{ fontWeight: 500, textTransform: "none", "& .MuiChip-icon": { fontSize: 18 } }}
      />
    );
  };

  const loadSubgraph = async (rootId: string) => {
    setSelectedRootId(rootId);

    // If you already have a graph loaded, just keep it for now.
    // Later we’ll swap this to server-side slicing.
    if (!graph) {
      try {
        const g = await api.getArtifactJson(selectedJobId!, "graph_full");
        setGraph(g.data);
      } catch (e) {
        enqueueSnackbar("No graph available yet", { variant: "warning" });
      }
    }
  };

  return (
    <Box sx={{ height: "100%", minHeight: 0, display: "flex" , p:1}}>
      {/* Collapsible left sidebar */}
      <Sidebar open={sidebarOpen}>
        <Paper
          sx={{
            height: "100%",
            minHeight: 0,
            display: "flex",
            flexDirection: "column",
            borderRight: "1px solid",
            borderColor: "divider",
          }}
        >
          <Box sx={{ display: "flex", alignItems: "center", px: 1, py: 1 }}>
            <Typography variant="subtitle1" sx={{ flex: 1, fontWeight: 600 }}>
              Ignition Graph
            </Typography>
            <Tooltip title="Hide sidebar" arrow>
              <IconButton size="small" onClick={() => setSidebarOpen(false)}>
                <ChevronLeftIcon fontSize="small" />
              </IconButton>
            </Tooltip>
          </Box>
          <Divider />

          <Box sx={{ p: 1, pt: 1, overflow: "auto", flex: 1, minHeight: 0 }}>
            <Stack spacing={2} sx={{ minHeight: 0 }}>
              <Card>
                <CardContent sx={{ display: "flex", flexDirection: "column", gap: 1.5 }}>
                  <Typography variant="subtitle2">Run Ignition Graph</Typography>
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
                  <List dense disablePadding sx={{ minHeight: 0 }}>
                    {recent.map((r) => {
                      const statusColor =
                        r.status === "success" ? "success" :
                        r.status === "error"   ? "error"   :
                        r.status === "running" ? "info"    :
                        r.status === "queued"  ? "warning" :
                        "default";

                      // Shorten jobId: first 4 chars + last 4 chars
                      const shortId = `${r.jobId.slice(0, 4)}…${r.jobId.slice(-4)}`;

                      const formattedTime = new Date(r.createdAt)
                        .toLocaleString("en-GB", {
                          day: "2-digit",
                          month: "short",
                          year: "2-digit",
                          hour: "2-digit",
                          minute: "2-digit",
                          second: "2-digit",
                          hour12: false
                        })
                        .replace(/ /g, "-")
                        .replace(",", "");

                      return (
                        <ListItemButton
                          key={r.jobId}
                          selected={selectedJobId === r.jobId}
                          onClick={() => {
                            setSelectedJobId(r.jobId);
                            setSidebarOpen(false);

                            setGraph(null);
                            setReport(null);
                            setSummary("");
                            setTree(null);
                            setTreeError("");
                            setSelectedRootId(null);
                          }}
                          sx={{
                            py: 0.5,
                            px: 1,
                            display: "flex",
                            alignItems: "center",
                            gap: 1,
                          }}
                        >
                          <ListItemText
                            primary={
                              <Stack direction="row" alignItems="center" spacing={1}>
                                {/* Clickable short jobId */}
                                <Typography
                                  variant="body2"
                                  sx={{
                                    fontFamily: "monospace",
                                    cursor: "pointer",
                                    textDecoration: "underline",
                                    textUnderlineOffset: 3,
                                  }}
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    setSelectedJobId(r.jobId);
                                  }}
                                >
                                  {shortId}
                                </Typography>

                                {/* Status chip */}
                                <Chip
                                  label={r.status}
                                  size="small"
                                  color={statusColor}
                                  sx={{ textTransform: "capitalize" }}
                                />

                                {/* Timestamp */}
                                <Typography
                                  variant="caption"
                                  color="text.secondary"
                                  sx={{ fontFamily: "monospace" }}
                                >
                                  {formattedTime}
                                </Typography>
                              </Stack>
                            }
                            secondary={
                              <Typography
                                variant="caption"
                                color="text.secondary"
                                sx={{ fontFamily: "monospace" }}
                              >
                                {r.toolId}
                              </Typography>
                            }
                          />

                          {/* Copy button */}
                          <Tooltip title="Copy job ID">
                            <IconButton
                              size="small"
                              edge="end"
                              onClick={(e) => {
                                e.stopPropagation();
                                navigator.clipboard.writeText(r.jobId);
                                enqueueSnackbar("Copied job ID", { variant: "success" });
                              }}
                            >
                              <ContentCopyIcon fontSize="small" />
                            </IconButton>
                          </Tooltip>
                        </ListItemButton>
                      );
                    })}
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
          </Box>
        </Paper>
      </Sidebar>

      {/* Main workspace */}
      <Box sx={{ flex: 1, minWidth: 0, minHeight: 0, display: "flex", flexDirection: "column",  marginLeft: 1 }}>
        <Paper sx={{ flex: 1, minHeight: 0, display: "flex", flexDirection: "column" }}>
          <Box sx={{ p: 1.25, display: "flex", alignItems: "center", gap: 1.5 }}>
            {!sidebarOpen && (
              <Tooltip title="Show sidebar" arrow>
                <IconButton size="small" onClick={() => setSidebarOpen(true)}>
                  <MenuIcon fontSize="small" />
                </IconButton>
              </Tooltip>
            )}

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
                    minHeight: 0,
                  }}
                >
                  {/* <Box sx={{ p: 1, display: "flex", flexDirection: "column", gap: 1 }}>
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
                  </Box> */}

                  <Divider />
                  <Box sx={{ flex: 1, minHeight: 0 }}>
                    <ProjectExplorerTree
                      key={selectedJobId || "tree"}
                      tree={tree}
                      selectedId={selectedRootId}
                      onSelect={loadSubgraph}
                    />
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
                      : tree
                        ? "Explorer loaded"
                        : "Waiting for artifacts..."}
                </Typography>
              </Box>
            )}
          </Box>
        </Paper>
      </Box>
    </Box>
  );
}
