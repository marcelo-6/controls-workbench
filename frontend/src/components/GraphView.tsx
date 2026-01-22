// src/components/GraphView.tsx
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
  FormControlLabel,
  Slider
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
  applyEdgeChanges,
} from "reactflow";
import { useTheme } from "@mui/material/styles";

import { api } from "../api/client";
import { layoutDagre, type DagreLayoutOptions } from "../utils/layout";
import ResourceNode from "./ResourceNode";
import NodeInspectorDrawer from "./NodeInspectorDrawer";
import { useArtifactIndex } from "../hooks/useArtifactIndex";

type Props = {
  jobId?: string | null;
  graph: any; // Graph (GraphBundle.graph_ui)
  report: any | null; // legacy, optional
  summary: string; // legacy, optional
};

type GroupBy = "type" | "section";
type FilterMode = "strict" | "neighbors";

type SelectedDetails = {
  node: any;      // GraphNode
  inbound: any[]; // GraphEdge[]
  outbound: any[];// GraphEdge[]
};


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
    const thumbnailKind = `node:${n.id}:thumbnail`;
    const thumbnailUrl = jobId ? api.artifactHref(jobId, thumbnailKind) : null;

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
    animated: false,
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

  // ---- NEW: edge confidence cutoff
  const [edgeMinConfidence, setEdgeMinConfidence] = useState(0.0);

  // ---- RF state
  const [nodes, setNodes] = useNodesState<Node>([]);
  const [edges, setEdges] = useEdgesState<Edge>([]);

  // ---- Selection
  const [selected, setSelected] = useState<SelectedDetails | null>(null);

  // ---- Summary dialog (Phase 1)
  const [summaryOpen, setSummaryOpen] = useState(false);
  const [summaryLoading, setSummaryLoading] = useState(false);
  const [summaryErr, setSummaryErr] = useState<string>("");
  const [summaryData, setSummaryData] = useState<any | null>(null);

  // ---- Phase 2: artifacts index
  const { byNodeId: artifactsByNodeId } = useArtifactIndex(jobId);

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

  // Initial layout on graph load
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

    // adjacency for neighbors mode (based on confidence-filtered edges)
    const adj = new Map<string, Set<string>>();

    const confidenceFilteredEdges = edges.filter((e) => {
      const c = (e.data as any)?.confidence ?? 1.0;
      return c >= edgeMinConfidence;
    });

    for (const e of confidenceFilteredEdges) {
      if (!adj.has(e.source)) adj.set(e.source, new Set());
      if (!adj.has(e.target)) adj.set(e.target, new Set());
      adj.get(e.source)!.add(e.target);
      adj.get(e.target)!.add(e.source);
    }

    const baseKept = new Set<string>();

    for (const n of nodes) {
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

    // edges are already confidence-filtered for the visible graph
    const es = confidenceFilteredEdges.filter((e) => kept.has(e.source) && kept.has(e.target));

    return { nodes: ns, edges: es, keptIds: kept };
  }, [nodes, edges, typeFilter, search, filterMode, groupBy, edgeMinConfidence]);

  useEffect(() => {
    if (!selected?.node?.id) return;
    if (!filtered.keptIds.has(selected.node.id)) setSelected(null);
  }, [filtered.keptIds, selected]);

  const filtersActive =
    typeFilter.length > 0 ||
    searchInput.trim().length > 0 ||
    filterMode !== "neighbors" ||
    edgeMinConfidence > 0;

  const clearFilters = () => {
    setTypeFilter([]);
    setSearchInput("");
    setFilterMode("neighbors");
    setEdgeMinConfidence(0);
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
      const res = await api.getArtifactJson(jobId, "summary");
      setSummaryData(res?.data ?? res);
    } catch (e: any) {
      setSummaryErr(e.message || "Failed to load summary.json");
    } finally {
      setSummaryLoading(false);
    }
  };

  const nodeTypes = useMemo(() => ({ resource: ResourceNode }), []);

  const selectedNodeArtifacts = useMemo(() => {
    const nodeId = selected?.node?.id as string | undefined;
    if (!nodeId) return null;
    return artifactsByNodeId.get(nodeId) ?? null;
  }, [selected, artifactsByNodeId]);

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

          {/* NEW: confidence slider */}
          <Box sx={{ width: 220, px: 1 }}>
            <Typography variant="caption" color="text.secondary" sx={{ display: "block", mb: 0.25 }}>
              Edge confidence ≥ {edgeMinConfidence.toFixed(2)}
            </Typography>
            <Slider
              size="small"
              value={edgeMinConfidence}
              min={0}
              max={1}
              step={0.05}
              onChange={(_, v) => setEdgeMinConfidence(v as number)}
            />
          </Box>

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
            onNodesChange={(changes) => setNodes((nds) => applyNodeChanges(changes, nds))}
            onEdgesChange={(changes) => setEdges((eds) => applyEdgeChanges(changes, eds))}
            nodesDraggable
            nodesConnectable={false}
            elementsSelectable
            selectNodesOnDrag
            zoomOnScroll
            zoomOnPinch
            panOnScroll={false}
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

        {/* Layout panel (unchanged) */}
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

        {/* ✅ Phase 2 inspector drawer */}
        <NodeInspectorDrawer
          open={Boolean(selected)}
          onClose={() => setSelected(null)}
          jobId={jobId}
          selected={selected}
          nodeArtifacts={selectedNodeArtifacts}
          edgeMinConfidence={edgeMinConfidence}
          topOffsetPx={theme.mixins.toolbar.minHeight as number}
        />

        {/* Summary dialog (unchanged) */}
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

      </Box>
    </ReactFlowProvider>
  );
}
