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
import InfoOutlinedIcon from "@mui/icons-material/InfoOutlined";
import { useSnackbar } from "notistack";
import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  ReactFlowProvider,
  type Edge,
  type Node,
  useReactFlow,
  useNodesState,
  useEdgesState,
  applyNodeChanges,
  applyEdgeChanges
} from "reactflow";
import { useTheme } from "@mui/material/styles";

import { api } from "../api/client";
import { layoutDagre, type DagreLayoutOptions } from "../utils/layout";
import ResourceNode from "./ResourceNode";

type Props = {
  jobId?: string | null;
  graph: any; // Graph (GraphBundle.graph_ui)
  report: any | null; // legacy, optional
  summary: string; // legacy, optional
};

type GroupBy = "type" | "section";
type FilterMode = "strict" | "neighbors";

type SelectedDetails = {
  node: any; // GraphNode
  inbound: any[]; // GraphEdge[]
  outbound: any[]; // GraphEdge[]
};

function artifactUrl(jobId: string, relPath: string) {
  // NOTE: keep consistent with your backend routes
  // You previously used /api/jobs/<id>/artifact?path=...
  // Here you use /api/runs/<id>/artifacts/<relPath>
  // Keep whatever is correct for your backend.
  return `/api/runs/${jobId}/artifacts/${encodeURIComponent(relPath)}`;
}

function nodeSection(n: any): string | null {
  const meta = n?.metadata ?? {};
  if (meta?.section) return String(meta.section);

  const tags: string[] = n?.tags ?? [];
  const secTag = tags.find((t) => String(t).toLowerCase().startsWith("section:"));
  if (secTag) return String(secTag).split(":").slice(1).join(":") || null;

  return null;
}

function nodeKind(n: any, groupBy: GroupBy = "type"): string {
  if (groupBy === "section") {
    return nodeSection(n) ?? "Other";
  }
  return (n?.type || "resource") as string;
}

function toRfNodes(graphNodes: any[], jobId?: string | null): Node[] {
  return (graphNodes || []).map((n) => {
    // Thumbnails exist for many nodes as: nodes/<id>/thumbnail.png
    const thumbnailUrl = jobId ? artifactUrl(jobId, `node:${n.id}:thumbnail`) : null;

    return {
      id: n.id,
      type: "resource",
      position: n.position || { x: 0, y: 0 },
      data: {
        // GraphNode contract fields
        id: n.id,
        label: n.label,
        nodeType: n.type,
        path: n.path ?? null,
        parentId: n.parent_id ?? null,
        status: n.status ?? "live",
        tags: n.tags ?? [],
        description: n.description ?? null,
        details: n.details ?? null,
        tooltip: n.tooltip ?? null,
        metadata: n.metadata ?? {},

        // UI helpers
        thumbnailUrl,
        raw: n
      },
      style: { width: 280 }
    };
  });
}

function toRfEdges(graphEdges: any[]): Edge[] {
  return (graphEdges || []).map((e) => ({
    id: e.id,
    source: e.source,
    target: e.target,
    label: e.type,
    animated: false, //(e.confidence ?? 1.0) >= 0.85,
    data: {
      type: e.type,
      confidence: e.confidence ?? 1.0,
      evidence: e.evidence ?? null,
      metadata: e.metadata ?? {},
      raw: e
    }
  }));
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

function formatConfidence(x: any): string {
  const v = typeof x === "number" ? x : Number(x ?? 1);
  if (Number.isNaN(v)) return "—";
  return v.toFixed(2);
}

function prettyEdgeLabel(t: any): string {
  const s = String(t || "references");
  return s.replace(/_/g, " ");
}

function KeyValueBlock({ obj }: { obj: any }) {
  return (
    <Box
      sx={{
        fontFamily: "ui-monospace, monospace",
        fontSize: 12,
        whiteSpace: "pre-wrap",
        overflow: "auto",
        border: "1px solid",
        borderColor: "divider",
        borderRadius: 2,
        p: 1,
        maxHeight: 220
      }}
    >
      {JSON.stringify(obj ?? {}, null, 2)}
    </Box>
  );
}

function EdgeList({
  title,
  edges
}: {
  title: string;
  edges: any[];
}) {
  return (
    <Box>
      <Typography variant="subtitle2">
        {title} ({edges.length})
      </Typography>

      <Stack spacing={1} sx={{ mt: 1 }}>
        {edges.slice(0, 80).map((e) => (
          <Box
            key={e.id}
            sx={{
              border: "1px solid",
              borderColor: "divider",
              borderRadius: 1.5,
              p: 1
            }}
          >
            <Typography variant="body2" sx={{ fontFamily: "ui-monospace, monospace" }}>
              {prettyEdgeLabel(e.type)} • conf {formatConfidence(e.confidence)}
            </Typography>
            {e.evidence ? (
              <Typography variant="caption" color="text.secondary" sx={{ display: "block" }}>
                {e.evidence}
              </Typography>
            ) : null}
          </Box>
        ))}
        {edges.length > 80 ? (
          <Typography variant="caption" color="text.secondary">
            Showing first 80 edges…
          </Typography>
        ) : null}
      </Stack>
    </Box>
  );
}

export default function GraphView({ jobId, graph, report, summary }: Props) {
  const { enqueueSnackbar } = useSnackbar();
  const theme = useTheme();
  const isDark = theme.palette.mode === "dark";

  const [fitVersion, setFitVersion] = useState(0);

  // ---- Grouping
  const [groupBy, setGroupBy] = useState<GroupBy>("type");

  // ---- Layout options
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

  // ---- Filters
  const [typeFilter, setTypeFilter] = useState<string[]>([]);
  const [searchInput, setSearchInput] = useState("");
  const search = useDeferredValue(searchInput);
  const [filterMode, setFilterMode] = useState<FilterMode>("neighbors");

  // ---- RF state
  // const [nodes, setNodes] = useState<Node[]>([]);
  // const [edges, setEdges] = useState<Edge[]>([]);
  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
  // ---- Selection (Phase 1: local graph only)
  const [selected, setSelected] = useState<SelectedDetails | null>(null);

  // ---- Issues dialog (legacy)
  const [issuesOpen, setIssuesOpen] = useState(false);

  // ---- Summary dialog (Phase 1 + Summary button)
  const [summaryOpen, setSummaryOpen] = useState(false);
  const [summaryLoading, setSummaryLoading] = useState(false);
  const [summaryErr, setSummaryErr] = useState<string>("");
  const [summaryData, setSummaryData] = useState<any | null>(null);

  

  const nodeById = useMemo(() => {
    const m = new Map<string, any>();
    for (const n of graph?.nodes || []) m.set(n.id, n);
    return m;
  }, [graph]);

  const edgesByNode = useMemo(() => {
    const inbound = new Map<string, any[]>();
    const outbound = new Map<string, any[]>();

    for (const e of graph?.edges || []) {
      if (!outbound.has(e.source)) outbound.set(e.source, []);
      if (!inbound.has(e.target)) inbound.set(e.target, []);
      outbound.get(e.source)!.push(e);
      inbound.get(e.target)!.push(e);
    }
    return { inbound, outbound };
  }, [graph]);

  const allTypes = useMemo(() => {
    const s = new Set<string>();
    (graph?.nodes || []).forEach((n: any) => s.add(nodeKind(n, groupBy)));
    return Array.from(s).sort();
  }, [graph, groupBy]);

  // Initial layout on graph load (do not reset filters on groupBy changes)
  useEffect(() => {
    if (!graph) return;

    const ns = toRfNodes(graph.nodes || [], jobId);
    const es = toRfEdges(graph.edges || []);

    const laid = layoutDagre(ns, es, layoutOpts);

    setNodes(laid.nodes);
    setEdges(laid.edges);

    setSelected(null);
    setFitVersion((v) => v + 1);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [graph, jobId]);

  const filtered = useMemo(() => {
    const lower = search.trim().toLowerCase();
    const allowedTypes = new Set(typeFilter);
    const keepType = (t: string) => (allowedTypes.size ? allowedTypes.has(t) : true);

    // adjacency for neighbors mode
    const adj = new Map<string, Set<string>>();
    for (const e of edges) {
      if (!adj.has(e.source)) adj.set(e.source, new Set());
      if (!adj.has(e.target)) adj.set(e.target, new Set());
      adj.get(e.source)!.add(e.target);
      adj.get(e.target)!.add(e.source);
    }

    const baseKept = new Set<string>();

    for (const n of nodes) {
      // IMPORTANT: filter key should match groupBy choice
      const raw = (n.data as any)?.raw;
      const kind = raw ? nodeKind(raw, groupBy) : (n.data as any)?.nodeType ?? "resource";
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
  }, [nodes, edges, typeFilter, search, filterMode, groupBy]);

  useEffect(() => {
    if (!selected?.node?.id) return;
    if (!filtered.keptIds.has(selected.node.id)) setSelected(null);
  }, [filtered.keptIds, selected]);

  const filtersActive =
    typeFilter.length > 0 || searchInput.trim().length > 0 || filterMode !== "neighbors";

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

    enqueueSnackbar(`Auto layout applied (${scope === "all" ? "all" : "visible"})`, {
      variant: "info"
    });
    setFitVersion((v) => v + 1);
  };

  const onNodeClick = (_: any, n: Node) => {
    const nodeId = n.id;
    const node = nodeById.get(nodeId) ?? (n.data as any)?.raw ?? null;
    if (!node) return;

    const inbound = edgesByNode.inbound.get(nodeId) ?? [];
    const outbound = edgesByNode.outbound.get(nodeId) ?? [];
    setSelected({ node, inbound, outbound });
  };

  const openSummary = async () => {
    if (!jobId) {
      enqueueSnackbar("No job selected", { variant: "warning" });
      return;
    }

    setSummaryOpen(true);

    if (summaryData) return;

    setSummaryLoading(true);
    setSummaryErr("");

    try {
      const res = await api.getArtifactJson(jobId, "summary"); // kind="summary" -> summary.json
      setSummaryData(res?.data ?? res);
    } catch (e: any) {
      setSummaryErr(e.message || "Failed to load summary.json");
    } finally {
      setSummaryLoading(false);
    }
  };

  const issues = report?.issues || {};
  const orphanCount = (issues.orphans || []).length;
  const brokenCount = (issues.broken_refs || []).length;
  const cyclesCount = (issues.cycles || []).length;

  const nodeTypes = useMemo(() => ({ resource: ResourceNode }), []);

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

          <Button
            size="small"
            variant="outlined"
            startIcon={<InfoOutlinedIcon />}
            onClick={openSummary}
            disabled={!jobId}
          >
            Summary
          </Button>

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
            variant="contained"
            color="primary"
            sx={{ textTransform: "none" }}
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
        <Box sx={{ flex: 1, minHeight: 0, pointerEvents: "auto" }}>
            <ReactFlow
              nodes={filtered.nodes}
              edges={filtered.edges}
              nodeTypes={nodeTypes}
              onNodeClick={onNodeClick}
              fitView
              fitViewOptions={{ padding: 0.25 }}
              onNodesChange={(changes) => {
                // update the *master* nodes state (not filtered)
                setNodes((nds) => applyNodeChanges(changes, nds));
              }}
              onEdgesChange={(changes) => {
                setEdges((eds) => applyEdgeChanges(changes, eds));
              }}
              // ✅ interactivity knobs
              nodesDraggable
              nodesConnectable={false}   // keep false if you don't want users creating edges
              elementsSelectable
              selectNodesOnDrag
              // panOnDrag={[1, 2]}         // left + middle mouse pan
              zoomOnScroll
              zoomOnPinch
              panOnScroll={false}        // change to true if you prefer trackpad scroll to pan
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
        <Drawer
          anchor="right"
          open={layoutOpen}
          onClose={() => setLayoutOpen(false)}
          PaperProps={{
            sx: (t) => ({
              top: t.mixins.toolbar.minHeight,
              height: `calc(100% - ${t.mixins.toolbar.minHeight}px)`
            })
          }}
        >
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
              control={
                <Switch checked={layoutAll} onChange={(e) => setLayoutAll(e.target.checked)} />
              }
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
                px: 1.25
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
        <Drawer
          anchor="right"
          open={Boolean(selected)}
          onClose={() => setSelected(null)}
          PaperProps={{
            sx: (t) => ({
              top: t.mixins.toolbar.minHeight,
              height: `calc(100% - ${t.mixins.toolbar.minHeight}px)`
            })
          }}
        >
          <Box sx={{ width: 460, p: 2, display: "flex", flexDirection: "column", gap: 1 }}>
            <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
              <Typography variant="h6" sx={{ flex: 1 }}>
                Node inspector
              </Typography>
              <IconButton onClick={() => setSelected(null)}>
                <CloseIcon />
              </IconButton>
            </Box>

            {selected?.node ? (
              <>
                {/* Overview */}
                <Typography variant="subtitle2">{selected.node.label}</Typography>
                <Typography variant="caption" color="text.secondary">
                  {selected.node.type} • status {selected.node.status}
                </Typography>

                {selected.node.path ? (
                  <Typography variant="body2" sx={{ fontFamily: "ui-monospace, monospace" }}>
                    {selected.node.path}
                  </Typography>
                ) : null}

                {selected.node.tooltip ? (
                  <Typography variant="caption" color="text.secondary">
                    {selected.node.tooltip}
                  </Typography>
                ) : null}

                {selected.node.description ? (
                  <Typography variant="caption" color="text.secondary">
                    {selected.node.description}
                  </Typography>
                ) : null}

                <Divider />

                {/* Tags */}
                <Typography variant="subtitle2">Tags</Typography>
                <Box sx={{ display: "flex", flexWrap: "wrap", gap: 0.75 }}>
                  {(selected.node.tags || []).length ? (
                    (selected.node.tags || []).map((t: string) => (
                      <Chip key={t} size="small" label={t} variant="outlined" />
                    ))
                  ) : (
                    <Typography variant="caption" color="text.secondary">
                      —
                    </Typography>
                  )}
                </Box>

                <Divider />

                {/* Metadata */}
                <Typography variant="subtitle2">Metadata</Typography>
                <KeyValueBlock obj={selected.node.metadata} />

                <Divider />

                {/* Relationships */}
                <Typography variant="subtitle2">
                  Relationships (in {selected.inbound.length} / out {selected.outbound.length})
                </Typography>

                <EdgeList title="Inbound" edges={selected.inbound} />
                <Divider />
                <EdgeList title="Outbound" edges={selected.outbound} />

                <Divider />

                {/* Raw */}
                <Typography variant="subtitle2">Raw node</Typography>
                <KeyValueBlock obj={selected.node} />
              </>
            ) : null}
          </Box>
        </Drawer>

        {/* Summary dialog */}
        <Dialog open={summaryOpen} onClose={() => setSummaryOpen(false)} fullWidth maxWidth="md">
          <DialogTitle sx={{ display: "flex", alignItems: "center", gap: 1 }}>
            Summary
            <Box sx={{ flex: 1 }} />
            <IconButton onClick={() => setSummaryOpen(false)}>
              <CloseIcon />
            </IconButton>
          </DialogTitle>

          <DialogContent dividers sx={{ minHeight: 420 }}>
            {summaryLoading ? (
              <Typography variant="body2" color="text.secondary">
                Loading summary…
              </Typography>
            ) : summaryErr ? (
              <Typography variant="body2" color="error">
                {summaryErr}
              </Typography>
            ) : !summaryData ? (
              <Typography variant="body2" color="text.secondary">
                No summary loaded.
              </Typography>
            ) : (
              <Stack spacing={2}>
                <Box>
                  <Typography variant="subtitle2">Meta</Typography>
                  <Typography variant="caption" color="text.secondary" display="block">
                    tool_id: {summaryData.tool_id}
                  </Typography>
                  <Typography variant="caption" color="text.secondary" display="block">
                    generated_at: {summaryData.generated_at}
                  </Typography>
                </Box>

                <Divider />

                <Box>
                  <Typography variant="subtitle2">Project</Typography>
                  <KeyValueBlock obj={summaryData.project} />
                </Box>

                <Divider />

                <Box>
                  <Typography variant="subtitle2">Profile</Typography>
                  <KeyValueBlock obj={summaryData.profile} />
                </Box>

                <Divider />

                <Box>
                  <Typography variant="subtitle2">Stats</Typography>
                  <KeyValueBlock obj={summaryData.stats} />
                </Box>
              </Stack>
            )}
          </DialogContent>
        </Dialog>

        {/* Issues dialog (legacy) */}
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
                  <Typography variant="subtitle2">Orphans ({(report?.issues?.orphans || []).length})</Typography>
                  <Typography variant="caption" color="text.secondary">
                    Nodes with 0 inbound references (excluding missing nodes).
                  </Typography>
                  <Box sx={{ fontFamily: "ui-monospace, monospace", fontSize: 12, whiteSpace: "pre-wrap" }}>
                    {(report?.issues?.orphans || []).slice(0, 200).join("\n") || "—"}
                  </Box>
                </Box>

                <Divider />

                <Box>
                  <Typography variant="subtitle2">
                    Broken refs ({(report?.issues?.broken_refs || []).length})
                  </Typography>
                  <Box sx={{ fontFamily: "ui-monospace, monospace", fontSize: 12, whiteSpace: "pre-wrap" }}>
                    {JSON.stringify((report?.issues?.broken_refs || []).slice(0, 100), null, 2)}
                  </Box>
                </Box>

                <Divider />

                <Box>
                  <Typography variant="subtitle2">
                    Cycles ({(report?.issues?.cycles || []).length})
                  </Typography>
                  <Box sx={{ fontFamily: "ui-monospace, monospace", fontSize: 12, whiteSpace: "pre-wrap" }}>
                    {JSON.stringify((report?.issues?.cycles || []).slice(0, 50), null, 2)}
                  </Box>
                </Box>

                <Divider />

                <Box>
                  <Typography variant="subtitle2">Summary (legacy)</Typography>
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
