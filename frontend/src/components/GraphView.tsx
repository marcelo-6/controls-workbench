import React, { useEffect, useMemo, useState } from "react";
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
  Typography
} from "@mui/material";
import CloseIcon from "@mui/icons-material/Close";
import AutoAwesomeIcon from "@mui/icons-material/AutoAwesome";
import BugReportIcon from "@mui/icons-material/BugReport";
import { useSnackbar } from "notistack";
import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  ReactFlowProvider,
  type Edge,
  type Node
} from "reactflow";

import { layoutDagre } from "../utils/layout";

type Props = {
  graph: any;
  report: any | null;
  summary: string;
};

function toRfNodes(graphNodes: any[]): Node[] {
  return graphNodes.map((n) => ({
    id: n.id,
    position: n.position || { x: 0, y: 0 },
    data: {
      label: n.label,
      subtitle: n.type,
      path: n.path,
      raw: n
    },
    style: {
      borderRadius: 12,
      border: "1px solid rgba(255,255,255,0.12)",
      padding: 10,
      width: 220
    }
  }));
}

function toRfEdges(graphEdges: any[]): Edge[] {
  return graphEdges.map((e) => ({
    id: e.id,
    source: e.source,
    target: e.target,
    animated: e.confidence === "high",
    label: e.type,
    data: e
  }));
}

export default function GraphView({ graph, report, summary }: Props) {
  const { enqueueSnackbar } = useSnackbar();

  const allTypes = useMemo(() => {
    const s = new Set<string>();
    (graph.nodes || []).forEach((n: any) => s.add(n.type));
    return Array.from(s).sort();
  }, [graph]);

  const [typeFilter, setTypeFilter] = useState<string[]>([]);
  const [search, setSearch] = useState("");

  const [nodes, setNodes] = useState<Node[]>([]);
  const [edges, setEdges] = useState<Edge[]>([]);
  const [selected, setSelected] = useState<any | null>(null);

  const [issuesOpen, setIssuesOpen] = useState(false);

  useEffect(() => {
    const ns = toRfNodes(graph.nodes || []);
    const es = toRfEdges(graph.edges || []);
    const laid = layoutDagre(ns, es, "LR");
    setNodes(laid.nodes);
    setEdges(laid.edges);
    setTypeFilter([]);
    setSearch("");
    setSelected(null);
  }, [graph]);

  const filtered = useMemo(() => {
    const lower = search.trim().toLowerCase();
    const allowedTypes = new Set(typeFilter);
    const keepType = (t: string) => (allowedTypes.size ? allowedTypes.has(t) : true);

    const keptNodeIds = new Set(
      (graph.nodes || [])
        .filter((n: any) => {
          if (!keepType(n.type)) return false;
          if (!lower) return true;
          const hay = `${n.label} ${n.path} ${n.type}`.toLowerCase();
          return hay.includes(lower);
        })
        .map((n: any) => n.id)
    );

    const ns = nodes.filter((n) => keptNodeIds.has(n.id));
    const es = edges.filter((e) => keptNodeIds.has(e.source) && keptNodeIds.has(e.target));
    return { nodes: ns, edges: es };
  }, [nodes, edges, graph, typeFilter, search]);

  const autoLayout = () => {
    const laid = layoutDagre(filtered.nodes, filtered.edges, "LR");
    setNodes((prev) => {
      const pos = new Map(laid.nodes.map((n) => [n.id, n.position]));
      return prev.map((n) => ({ ...n, position: pos.get(n.id) || n.position }));
    });
    enqueueSnackbar("Auto layout applied", { variant: "info" });
  };

  const issues = report?.issues || {};
  const orphanCount = (issues.orphans || []).length;
  const brokenCount = (issues.broken_refs || []).length;
  const cyclesCount = (issues.cycles || []).length;

  return (
    <ReactFlowProvider>
      <Box sx={{ height: "100%", display: "flex", flexDirection: "column" }}>
        <Box sx={{ p: 1, display: "flex", gap: 1, alignItems: "center", flexWrap: "wrap" }}>
          <TextField
            size="small"
            placeholder="Search nodes (label/path)"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            sx={{ minWidth: 260 }}
          />

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

          <Button size="small" startIcon={<AutoAwesomeIcon />} onClick={autoLayout}>
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

        <Box sx={{ flex: 1, minHeight: 0 }}>
          <ReactFlow
            nodes={filtered.nodes}
            edges={filtered.edges}
            fitView
            onNodeClick={(_, n) => setSelected(n.data.raw)}
          >
            <MiniMap />
            <Controls />
            <Background />
          </ReactFlow>
        </Box>

        <Drawer anchor="right" open={Boolean(selected)} onClose={() => setSelected(null)}>
          <Box sx={{ width: 420, p: 2, display: "flex", flexDirection: "column", gap: 1 }}>
            <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
              <Typography variant="h6" sx={{ flex: 1 }}>
                Node
              </Typography>
              <IconButton onClick={() => setSelected(null)}>
                <CloseIcon />
              </IconButton>
            </Box>
            {selected && (
              <>
                <Typography variant="subtitle2">{selected.label}</Typography>
                <Typography variant="caption" color="text.secondary">
                  {selected.type}
                </Typography>
                <Divider />
                <Typography variant="body2" sx={{ fontFamily: "ui-monospace, monospace" }}>
                  {selected.path}
                </Typography>
                <Divider />
                <Typography variant="subtitle2">Raw</Typography>
                <Box
                  sx={{
                    fontFamily: "ui-monospace, monospace",
                    fontSize: 12,
                    whiteSpace: "pre",
                    overflow: "auto",
                    maxHeight: 420,
                    border: "1px solid rgba(255,255,255,0.12)",
                    borderRadius: 2,
                    p: 1
                  }}
                >
                  {JSON.stringify(selected, null, 2)}
                </Box>
              </>
            )}
          </Box>
        </Drawer>

        <Dialog open={issuesOpen} onClose={() => setIssuesOpen(false)} fullWidth maxWidth="lg">
          <DialogTitle sx={{ display: "flex", alignItems: "center", gap: 1 }}>
            Issues
            <Box sx={{ flex: 1 }} />
            <IconButton onClick={() => setIssuesOpen(false)}><CloseIcon /></IconButton>
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
