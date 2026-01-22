import React, { useEffect, useMemo, useState, useDeferredValue } from "react";
import {
  Box,
  Button,
  Chip,
  Dialog,
  DialogContent,
  DialogTitle,
  Divider,
  Drawer,
  IconButton,
  Stack,
  TextField,
  Typography,
  MenuItem,
  Switch,
  FormControlLabel
} from "@mui/material";
import CloseIcon from "@mui/icons-material/Close";
import AutoAwesomeIcon from "@mui/icons-material/AutoAwesome";
import BugReportIcon from "@mui/icons-material/BugReport";
import TuneIcon from "@mui/icons-material/Tune";
import { useSnackbar } from "notistack";
import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  ReactFlowProvider,
  type Edge,
  type Node,
  useReactFlow
} from "reactflow";
import { useTheme } from "@mui/material/styles";

import { api } from "../api/client";
import { layoutDagre, type DagreLayoutOptions } from "../utils/layout";
import ResourceNode from "./ResourceNode";

type Props = {
  jobId?: string | null;
  graph: any;
  report: any | null;
  summary: string;
};
type GroupBy = "type" | "section";
const [groupBy, setGroupBy] = useState<GroupBy>("type");

function artifactUrl(jobId: string, relPath: string) {
  return `/api/runs/${jobId}/artifacts/${encodeURIComponent(relPath)}`;
}

function nodeSection(n: any): string | null {
  const meta = n?.metadata ?? n?.data ?? {};
  if (meta?.section) return String(meta.section);

  const tags: string[] = n?.tags ?? meta?.tags ?? [];
  const secTag = tags.find((t) => String(t).toLowerCase().startsWith("section:"));
  if (secTag) return String(secTag).split(":").slice(1).join(":") || null;

  return null;
}

function nodeKind(n: any, groupBy: "type" | "section" = "type"): string {
  if (groupBy === "section") {
    return nodeSection(n) ?? "Other";
  }
  // groupBy === "type"
  return (n?.data?.kind || n?.type || "resource") as string;
}



function deriveThumbnailRelPath(nodeId: string) {
  return `node:${nodeId}:thumbnail`;
}

function toRfNodes(graphNodes: any[], jobId?: string | null, groupBy: "type" | "section" = "type"): Node[] {
  return (graphNodes || []).map((n) => {
    const kind = nodeKind(n, groupBy);

    // Support either node.data.* or "metadata/tags/status/tooltip" top-level
    const meta = n?.data ?? n?.metadata ?? {};
    const tags = n?.tags ?? meta?.tags ?? [];
    const status = n?.status ?? meta?.status ?? null;
    const description = n?.description ?? meta?.description ?? null;
    const tooltip = n?.tooltip ?? n?.path ?? "";

    // Prefer explicit thumbnail_path if present, otherwise derive it.
    const thumbPath =
      n?.data?.thumbnail_path ??
      meta?.thumbnail_path ??
      (n?.id ? deriveThumbnailRelPath(n.id) : null);

    const thumbnailUrl = jobId && thumbPath ? artifactUrl(jobId, thumbPath) : null;

    // Fan-in/out metrics might exist in n.data.metrics OR meta.metrics OR be absent
    const metrics = n?.data?.metrics ?? meta?.metrics ?? undefined;

    return {
      id: n.id,
      type: "resource",
      position: n.position || { x: 0, y: 0 },
      data: {
        label: n.label,
        kind,
        path: n.path,
        tooltip,
        status,
        description,
        tags,
        metrics,
        thumbnailUrl,
        raw: n
      },
      style: { width: 280 }
    };
  });
}


function toRfEdges(graphEdges: any[]): Edge[] {
  return (graphEdges || []).map((e) => {
    const { score, level } = normalizeConfidence(e.confidence);

    return {
      id: e.id,
      source: e.source,
      target: e.target,
      animated: level === "high" || score >= 0.85,
      label: prettyEdgeLabel(e.type),
      data: {
        ...e,
        confidenceScore: score,
        confidenceLevel: level
      }
    };
  });
}


function FitOnVersion({ version }: { version: number }) {
  const { fitView } = useReactFlow();

  useEffect(() => {
    const t = window.setTimeout(() => {
      fitView({ padding: 0.12, duration: 250 });
    }, 0);
    return () => window.clearTimeout(t);
  }, [version, fitView]);

  return null;
}

function normalizeConfidence(c: any): { score: number; level: "high" | "medium" | "low" } {
  // Accept: "high" | "medium" | "low" OR number 0..1 OR int 0/1/2/3 etc.
  if (typeof c === "string") {
    const v = c.toLowerCase();
    if (v === "high") return { score: 1.0, level: "high" };
    if (v === "medium") return { score: 0.6, level: "medium" };
    return { score: 0.3, level: "low" };
  }
  if (typeof c === "number") {
    const score = c > 1 ? Math.max(0, Math.min(1, c / 3)) : Math.max(0, Math.min(1, c));
    const level = score >= 0.8 ? "high" : score >= 0.5 ? "medium" : "low";
    return { score, level };
  }
  return { score: 0.3, level: "low" };
}

function prettyEdgeLabel(t: any): string {
  const s = String(t || "references");
  return s.replace(/_/g, " ");
}


type FilterMode = "strict" | "neighbors";

export default function GraphView({ jobId, graph, report, summary }: Props) {
  const { enqueueSnackbar } = useSnackbar();
  const theme = useTheme();
  const isDark = theme.palette.mode === "dark";

  const [fitVersion, setFitVersion] = useState(0);

  // ----- Layout options
  const [layoutOpen, setLayoutOpen] = useState(false);
  const [layoutAll, setLayoutAll] = useState(false);
  const [layoutOpts, setLayoutOpts] = useState<DagreLayoutOptions>({
    direction: "TB",
    nodeSep: 150,
    rankSep: 250,
    ranker: "network-simplex",
    align: "UL",
    marginX: 40,
    marginY: 40
  });

  // ----- Filters
  const [typeFilter, setTypeFilter] = useState<string[]>([]);
  const [searchInput, setSearchInput] = useState("");
  const search = useDeferredValue(searchInput);
  const [filterMode, setFilterMode] = useState<FilterMode>("neighbors");

  // ----- RF state
  const [nodes, setNodes] = useState<Node[]>([]);
  const [edges, setEdges] = useState<Edge[]>([]);

  // ----- Selection
  const [selected, setSelected] = useState<any | null>(null);
  const [selectedLoading, setSelectedLoading] = useState(false);

  const [issuesOpen, setIssuesOpen] = useState(false);

  const allTypes = useMemo(() => {
    const s = new Set<string>();
    (graph.nodes || []).forEach((n: any) => s.add(nodeKind(n, groupBy)));
    return Array.from(s).sort();
  }, [graph, groupBy]);


  // Initial layout on graph load
  useEffect(() => {
    const ns = toRfNodes(graph.nodes || [], jobId, groupBy);
    const es = toRfEdges(graph.edges || []);

    const laid = layoutDagre(ns, es, layoutOpts);

    setNodes(laid.nodes);
    setEdges(laid.edges);

    setTypeFilter([]);
    setSearchInput("");
    setSelected(null);

    setFitVersion((v) => v + 1);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [graph, jobId]);

  // Filtering is computed from *current* nodes/edges (not graph.nodes),
  // so it always matches what is rendered and what auto-layout modified.
  const filtered = useMemo(() => {
    const lower = search.trim().toLowerCase();
    const allowedTypes = new Set(typeFilter);
    const keepType = (t: string) => (allowedTypes.size ? allowedTypes.has(t) : true);

    // quick adjacency map for "neighbors" mode
    const adj = new Map<string, Set<string>>();
    for (const e of edges) {
      if (!adj.has(e.source)) adj.set(e.source, new Set());
      if (!adj.has(e.target)) adj.set(e.target, new Set());
      adj.get(e.source)!.add(e.target);
      adj.get(e.target)!.add(e.source);
    }

    const baseKept = new Set<string>();
    for (const n of nodes) {
      const kind = (n.data as any)?.kind ?? "resource";
      if (!keepType(kind)) continue;

      if (!lower) {
        baseKept.add(n.id);
        continue;
      }

      const label = ((n.data as any)?.label ?? "").toString();
      const path = ((n.data as any)?.path ?? "").toString();
      const hay = `${label} ${path} ${kind}`.toLowerCase();

      if (hay.includes(lower)) baseKept.add(n.id);
    }

    // Optional: include neighbors of matched nodes for context
    const kept = new Set(baseKept);
    if (filterMode === "neighbors" && baseKept.size) {
      for (const id of baseKept) {
        const ns = adj.get(id);
        if (!ns) continue;
        for (const nb of ns) kept.add(nb);
      }
    }

    const ns = nodes.filter((n) => kept.has(n.id));
    const es = edges.filter((e) => kept.has(e.source) && kept.has(e.target));

    return { nodes: ns, edges: es, keptIds: kept };
  }, [nodes, edges, typeFilter, search, filterMode]);

  // If selection is filtered out, close it to avoid confusion
  useEffect(() => {
    if (!selected?.node?.id) return;
    if (!filtered.keptIds.has(selected.node.id)) setSelected(null);
  }, [filtered.keptIds, selected]);

  const clearFilters = () => {
    setTypeFilter([]);
    setSearchInput("");
    setFilterMode("neighbors");
    enqueueSnackbar("Filters cleared", { variant: "info" });
  };

  const applyLayout = (scope: "visible" | "all") => {
    const targetNodes = scope === "all" ? nodes : filtered.nodes;
    const targetEdges = scope === "all" ? edges : filtered.edges;

    const laid = layoutDagre(targetNodes, targetEdges, layoutOpts);

    setNodes((prev) => {
      const pos = new Map(laid.nodes.map((n) => [n.id, n.position]));
      return prev.map((n) => ({ ...n, position: pos.get(n.id) || n.position }));
    });

    enqueueSnackbar(
      `Auto layout applied (${scope === "all" ? "all" : "visible"})`,
      { variant: "info" }
    );
    setFitVersion((v) => v + 1);
  };

  const onNodeClick = async (_: any, n: Node) => {
    const raw = (n.data as any)?.raw;
    setSelectedLoading(true);

    try {
      if (jobId) {
        const details = await api.getNodeDetails(jobId, n.id);
        setSelected(details);
      } else {
        setSelected({ node: raw, inbound: [], outbound: [] });
      }
    } catch (e: any) {
      enqueueSnackbar(e.message || "Failed to load node details", { variant: "error" });
      setSelected({ node: raw, inbound: [], outbound: [] });
    } finally {
      setSelectedLoading(false);
    }
  };

  const issues = report?.issues || {};
  const orphanCount = (issues.orphans || []).length;
  const brokenCount = (issues.broken_refs || []).length;
  const cyclesCount = (issues.cycles || []).length;

  const nodeTypes = useMemo(() => ({ resource: ResourceNode }), []);

  const filtersActive = typeFilter.length > 0 || searchInput.trim().length > 0 || filterMode !== "neighbors";

  return (
    <ReactFlowProvider>
      <Box sx={{ height: "100%", display: "flex", flexDirection: "column" }}>
        {/* Toolbar */}
        <Box sx={{ p: 1, display: "flex", gap: 1, alignItems: "center", flexWrap: "wrap" }}>
          <TextField
            size="small"
            placeholder="Search nodes (label/path)"
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            sx={{ minWidth: 260 }}
          />

          <TextField
            select
            size="small"
            label="Filter mode"
            value={filterMode}
            onChange={(e) => setFilterMode(e.target.value as FilterMode)}
            sx={{ width: 160 }}
          >
            <MenuItem value="neighbors">Include neighbors</MenuItem>
            <MenuItem value="strict">Strict match</MenuItem>
          </TextField>
          <TextField
            select
            size="small"
            label="Group by"
            value={groupBy}
            onChange={(e) => setGroupBy(e.target.value as GroupBy)}
            sx={{ width: 150 }}
          >
            <MenuItem value="type">Type</MenuItem>
            <MenuItem value="section">Section</MenuItem>
          </TextField>


          <Stack direction="row" spacing={1} sx={{ flexWrap: "wrap" }}>
            {allTypes.map((t) => {
              const on = typeFilter.includes(t);
              return (
                <Chip
                  key={t}
                  size="small"
                  label={t}
                  variant={on ? "filled" : "outlined"}
                  onClick={() => {
                    setTypeFilter((prev) =>
                      prev.includes(t) ? prev.filter((x) => x !== t) : [...prev, t]
                    );
                  }}
                />
              );
            })}
          </Stack>

          <Box sx={{ flex: 1 }} />

          {filtersActive && (
            <Button size="small" variant="outlined" onClick={clearFilters}>
              Clear
            </Button>
          )}

          <Button size="small" startIcon={<TuneIcon />} onClick={() => setLayoutOpen(true)}>
            Layout
          </Button>

          <Button
            size="small"
            startIcon={<AutoAwesomeIcon />}
            onClick={() => applyLayout(layoutAll ? "all" : "visible")}
          >
            Auto layout
          </Button>

          <Button
            size="small"
            startIcon={<BugReportIcon />}
            onClick={() => setIssuesOpen(true)}
            disabled={!report}
          >
            Issues ({orphanCount + brokenCount + cyclesCount})
          </Button>
        </Box>

        <Divider />

        {/* Graph */}
        <Box sx={{ flex: 1, minHeight: 0 }}>
          <ReactFlow
            nodes={filtered.nodes}
            edges={filtered.edges}
            fitView
            fitViewOptions={{ padding: 0.25 }}
            nodeTypes={nodeTypes}
            onNodeClick={onNodeClick}
            minZoom={0.02}
            maxZoom={4}
          >
            <FitOnVersion version={fitVersion} />
            <MiniMap
              maskColor={isDark ? "rgba(0,0,0,0.40)" : "rgba(0,0,0,0.08)"}
              nodeColor={isDark ? "rgba(250,250,250,0.45)" : "rgba(11,11,12,0.35)"}
              nodeStrokeColor={isDark ? "rgba(250,250,250,0.70)" : "rgba(11,11,12,0.55)"}
            />
            <Controls position="top-left" showZoom showFitView showInteractive />
            <Background />
          </ReactFlow>
        </Box>

        {/* Layout panel */}
        <Drawer anchor="right" open={layoutOpen} onClose={() => setLayoutOpen(false)}
            PaperProps={{
              sx: (theme) => ({
                top: theme.mixins.toolbar.minHeight,
                height: `calc(100% - ${theme.mixins.toolbar.minHeight}px)`,
              }),
            }}>
          <Box sx={{ width: 360, p: 2, display: "flex", flexDirection: "column", gap: 2 }}>
            <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
              <Typography variant="h6" sx={{ flex: 1 }}>
                Layout settings
              </Typography>
              <IconButton onClick={() => setLayoutOpen(false)}>
                <CloseIcon />
              </IconButton>
            </Box>

            <FormControlLabel
              control={<Switch checked={layoutAll} onChange={(e) => setLayoutAll(e.target.checked)} />}
              label="Auto layout all nodes (not just visible)"
            />

            <TextField
              select
              size="small"
              label="Direction"
              value={layoutOpts.direction ?? "LR"}
              onChange={(e) => setLayoutOpts((p) => ({ ...p, direction: e.target.value as any }))}
            >
              <MenuItem value="LR">Left → Right</MenuItem>
              <MenuItem value="RL">Right → Left</MenuItem>
              <MenuItem value="TB">Top → Bottom</MenuItem>
              <MenuItem value="BT">Bottom → Top</MenuItem>
            </TextField>

            <TextField
              select
              size="small"
              label="Ranker"
              value={layoutOpts.ranker ?? "network-simplex"}
              onChange={(e) => setLayoutOpts((p) => ({ ...p, ranker: e.target.value as any }))}
            >
              <MenuItem value="network-simplex">network-simplex (best)</MenuItem>
              <MenuItem value="tight-tree">tight-tree</MenuItem>
              <MenuItem value="longest-path">longest-path</MenuItem>
            </TextField>

            <TextField
              select
              size="small"
              label="Align"
              value={layoutOpts.align ?? "UL"}
              onChange={(e) => setLayoutOpts((p) => ({ ...p, align: e.target.value as any }))}
            >
              <MenuItem value="UL">UL</MenuItem>
              <MenuItem value="UR">UR</MenuItem>
              <MenuItem value="DL">DL</MenuItem>
              <MenuItem value="DR">DR</MenuItem>
            </TextField>

            <TextField
              size="small"
              label="nodeSep"
              type="number"
              value={layoutOpts.nodeSep ?? 60}
              onChange={(e) => setLayoutOpts((p) => ({ ...p, nodeSep: Number(e.target.value) }))}
            />

            <TextField
              size="small"
              label="rankSep"
              type="number"
              value={layoutOpts.rankSep ?? 110}
              onChange={(e) => setLayoutOpts((p) => ({ ...p, rankSep: Number(e.target.value) }))}
            />

            <Button
              size="small"
              variant="outlined"
              color="primary"
              startIcon={<AutoAwesomeIcon />}
              onClick={() => applyLayout(layoutAll ? "all" : "visible")}
              sx={{
                textTransform: "none",
                fontWeight: 600,
                borderRadius: 999,
                px: 1.25,
              }}
            >
              Auto layout now
            </Button>

            <Typography variant="caption" color="text.secondary">
              Tip: “network-simplex” + higher rankSep usually looks best for dense graphs.
            </Typography>
          </Box>
        </Drawer>

        {/* Node details drawer */}
        <Drawer anchor="right" open={Boolean(selected)} onClose={() => setSelected(null)}
            PaperProps={{
                        sx: (theme) => ({
                          top: theme.mixins.toolbar.minHeight,
                          height: `calc(100% - ${theme.mixins.toolbar.minHeight}px)`,
                        }),
                      }}>
          <Box sx={{ width: 460, p: 2, display: "flex", flexDirection: "column", gap: 1 }}>
            <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
              <Typography variant="h6" sx={{ flex: 1 }}>
                Node
              </Typography>
              <IconButton onClick={() => setSelected(null)}>
                <CloseIcon />
              </IconButton>
            </Box>

            {selectedLoading ? (
              <Typography variant="body2" color="text.secondary">
                Loading node details…
              </Typography>
            ) : selected?.node ? (
              <>
                <Typography variant="subtitle2">{selected.node.label}</Typography>
                <Typography variant="caption" color="text.secondary">
                  {nodeKind(selected.node)}
                </Typography>

                <Divider />

                <Typography variant="body2" sx={{ fontFamily: "ui-monospace, monospace" }}>
                  {selected.node.path}
                </Typography>

                <Divider />

                <Typography variant="subtitle2">
                  Links (in {selected.inbound?.length || 0} / out {selected.outbound?.length || 0})
                </Typography>

                <Box
                  sx={{
                    fontFamily: "ui-monospace, monospace",
                    fontSize: 12,
                    whiteSpace: "pre",
                    overflow: "auto",
                    maxHeight: 160,
                    border: "1px solid rgba(255,255,255,0.12)",
                    borderRadius: 2,
                    p: 1
                  }}
                >
                  {JSON.stringify(
                    {
                      inbound: (selected.inbound || []).slice(0, 50),
                      outbound: (selected.outbound || []).slice(0, 50)
                    },
                    null,
                    2
                  )}
                </Box>

                <Divider />
                <Typography variant="subtitle2">Raw</Typography>
                <Box
                  sx={{
                    fontFamily: "ui-monospace, monospace",
                    fontSize: 12,
                    whiteSpace: "pre",
                    overflow: "auto",
                    maxHeight: 360,
                    border: "1px solid rgba(255,255,255,0.12)",
                    borderRadius: 2,
                    p: 1
                  }}
                >
                  {JSON.stringify(selected.node, null, 2)}
                </Box>
              </>
            ) : null}
          </Box>
        </Drawer>

        {/* Issues dialog */}
        <Dialog open={issuesOpen} onClose={() => setIssuesOpen(false)} fullWidth maxWidth="lg">
          <DialogTitle sx={{ display: "flex", alignItems: "center", gap: 1 }}>
            Issues
            <Box sx={{ flex: 1 }} />
            <IconButton onClick={() => setIssuesOpen(false)}>
              <CloseIcon />
            </IconButton>
          </DialogTitle>
          <DialogContent dividers sx={{ height: 560 }}>
            {!report ? (
              <Typography variant="body2" color="text.secondary">
                No report loaded.
              </Typography>
            ) : (
              <Stack spacing={2}>
                <Box>
                  <Typography variant="subtitle2">Orphans ({orphanCount})</Typography>
                  <Typography variant="caption" color="text.secondary">
                    Nodes with 0 inbound references (excluding missing nodes).
                  </Typography>
                  <Box sx={{ fontFamily: "ui-monospace, monospace", fontSize: 12, whiteSpace: "pre-wrap" }}>
                    {(issues.orphans || []).slice(0, 200).join("\n") || "—"}
                  </Box>
                </Box>

                <Divider />

                <Box>
                  <Typography variant="subtitle2">Broken refs ({brokenCount})</Typography>
                  <Box sx={{ fontFamily: "ui-monospace, monospace", fontSize: 12, whiteSpace: "pre-wrap" }}>
                    {JSON.stringify((issues.broken_refs || []).slice(0, 100), null, 2)}
                  </Box>
                </Box>

                <Divider />

                <Box>
                  <Typography variant="subtitle2">Cycles ({cyclesCount})</Typography>
                  <Box sx={{ fontFamily: "ui-monospace, monospace", fontSize: 12, whiteSpace: "pre-wrap" }}>
                    {JSON.stringify((issues.cycles || []).slice(0, 50), null, 2)}
                  </Box>
                </Box>

                <Divider />

                <Box>
                  <Typography variant="subtitle2">Summary</Typography>
                  <Box sx={{ fontFamily: "ui-monospace, monospace", fontSize: 12, whiteSpace: "pre-wrap" }}>
                    {summary || "—"}
                  </Box>
                </Box>
              </Stack>
            )}
          </DialogContent>
        </Dialog>
      </Box>
    </ReactFlowProvider>
  );
}
