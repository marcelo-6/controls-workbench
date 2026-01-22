// src/components/NodeInspectorDrawer.tsx
import React, { useEffect, useMemo, useState } from "react";
import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Box,
  Chip,
  Divider,
  Drawer,
  IconButton,
  List,
  ListItemButton,
  ListItemText,
  Typography,
} from "@mui/material";
import CloseIcon from "@mui/icons-material/Close";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import { api } from "../api/client";
import ArtifactPreview from "./ArtifactPreview";

type SelectedDetails = {
  node: any; // GraphNode
  inbound: any[]; // GraphEdge[]
  outbound: any[]; // GraphEdge[]
};

type Props = {
  open: boolean;
  onClose: () => void;
  jobId: string | null | undefined;
  selected: SelectedDetails | null;
  edgeMinConfidence: number;
  topOffsetPx?: number;
};

function formatConfidence(x: any): string {
  const v = typeof x === "number" ? x : Number(x ?? 1);
  if (Number.isNaN(v)) return "—";
  return v.toFixed(2);
}

function prettyEdgeLabel(t: any): string {
  const s = String(t || "references");
  return s.replace(/_/g, " ");
}

function KeyValueBlock({ obj, maxHeight = 240 }: { obj: any; maxHeight?: number }) {
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
        maxHeight,
      }}
    >
      {JSON.stringify(obj ?? {}, null, 2)}
    </Box>
  );
}

function kindFor(nodeId: string, file: string) {
  return `node:${nodeId}:${file}`;
}

// resource.json may list "thumbnail.png" but our API uses "thumbnail"
function normalizeResourceFile(f: string) {
  if (f === "thumbnail.png") return "thumbnail";
  return f;
}

export default function NodeInspectorDrawer({
  open,
  onClose,
  jobId,
  selected,
  edgeMinConfidence,
  topOffsetPx,
}: Props) {
  const nodeId = selected?.node?.id as string | undefined;

  const nodeFiles: string[] = useMemo(() => {
    const files = (selected?.node?.metadata?.files ?? []) as any;
    return Array.isArray(files) ? (files as string[]) : [];
  }, [selected]);

  // ---- resource.json (deep dive)
  const [resourceLoading, setResourceLoading] = useState(false);
  const [resourceErr, setResourceErr] = useState("");
  const [resourceJson, setResourceJson] = useState<any | null>(null);

  // ---- preview selection (file suffix)
  const [activeFile, setActiveFile] = useState<string | null>(null);

  const filteredInbound = useMemo(() => {
    const arr = selected?.inbound ?? [];
    return arr
      .filter((e) => (e.confidence ?? 1.0) >= edgeMinConfidence)
      .slice()
      .sort((a, b) => (b.confidence ?? 1.0) - (a.confidence ?? 1.0));
  }, [selected, edgeMinConfidence]);

  const filteredOutbound = useMemo(() => {
    const arr = selected?.outbound ?? [];
    return arr
      .filter((e) => (e.confidence ?? 1.0) >= edgeMinConfidence)
      .slice()
      .sort((a, b) => (b.confidence ?? 1.0) - (a.confidence ?? 1.0));
  }, [selected, edgeMinConfidence]);

  // Load resource.json when drawer opens / node changes (only if node lists it)
  useEffect(() => {
    let alive = true;

    async function run() {
      setResourceErr("");
      setResourceJson(null);
      setActiveFile(null);

      if (!open || !jobId || !nodeId) return;

      const hasResource = nodeFiles.includes("resource.json");
      if (!hasResource) return;

      setResourceLoading(true);
      try {
        const kind = kindFor(nodeId, "resource.json");
        const res = await api.getArtifactJson(jobId, kind);
        if (!alive) return;
        setResourceJson(res?.data ?? res);
      } catch (e: any) {
        if (!alive) return;
        setResourceErr(e.message || "Failed to load resource.json");
      } finally {
        if (!alive) return;
        setResourceLoading(false);
      }
    }

    run();
    return () => {
      alive = false;
    };
  }, [open, jobId, nodeId, nodeFiles]);

  // Prefer showing files from graph metadata (authoritative for UI)
  const deepDiveFiles = useMemo(() => {
    // If you want to merge resource.json.files too, you can, but keep it simple:
    return nodeFiles.slice().sort();
  }, [nodeFiles]);

  // Optional: also show what resource.json claims (for diagnostics)
  const resourceClaimsFiles = useMemo(() => {
    const files: string[] = resourceJson?.files ?? [];
    return Array.isArray(files) ? files.map(normalizeResourceFile) : [];
  }, [resourceJson]);

  const activeKind = useMemo(() => {
    if (!nodeId || !activeFile) return null;
    return kindFor(nodeId, activeFile);
  }, [nodeId, activeFile]);

  return (
    <Drawer
      anchor="right"
      open={open}
      onClose={onClose}
      PaperProps={{
        sx: (t) => {
          const top = topOffsetPx ?? (t.mixins.toolbar.minHeight as number);
          return {
            top,
            height: `calc(100% - ${top}px)`,
          };
        },
      }}
    >
      <Box sx={{ width: 520, p: 2, display: "flex", flexDirection: "column", gap: 1 }}>
        <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
          <Typography variant="h6" sx={{ flex: 1 }}>
            Node inspector
          </Typography>
          <IconButton onClick={onClose}>
            <CloseIcon />
          </IconButton>
        </Box>

        {!selected?.node ? (
          <Typography variant="body2" color="text.secondary">
            No node selected.
          </Typography>
        ) : (
          <>
            {/* OVERVIEW */}
            <Accordion defaultExpanded>
              <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                <Typography variant="subtitle2">Overview</Typography>
              </AccordionSummary>
              <AccordionDetails>
                <Typography variant="subtitle2">{selected.node.label}</Typography>
                <Typography variant="caption" color="text.secondary" display="block">
                  {selected.node.type} • status {selected.node.status}
                </Typography>

                {selected.node.path ? (
                  <Typography variant="body2" sx={{ fontFamily: "ui-monospace, monospace", mt: 0.5 }}>
                    {selected.node.path}
                  </Typography>
                ) : null}

                {selected.node.tooltip ? (
                  <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 0.5 }}>
                    {selected.node.tooltip}
                  </Typography>
                ) : null}

                {selected.node.description ? (
                  <Typography variant="caption" color="text.secondary" display="block">
                    {selected.node.description}
                  </Typography>
                ) : null}

                {selected.node.details ? (
                  <Typography variant="caption" color="text.secondary" display="block">
                    {selected.node.details}
                  </Typography>
                ) : null}
              </AccordionDetails>
            </Accordion>

            {/* TAGS */}
            <Accordion defaultExpanded>
              <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                <Typography variant="subtitle2">Tags</Typography>
              </AccordionSummary>
              <AccordionDetails>
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
              </AccordionDetails>
            </Accordion>

            {/* METADATA */}
            <Accordion>
              <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                <Typography variant="subtitle2">Metadata</Typography>
              </AccordionSummary>
              <AccordionDetails>
                <KeyValueBlock obj={selected.node.metadata} />
              </AccordionDetails>
            </Accordion>

            {/* RELATIONSHIPS */}
            <Accordion>
              <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                <Typography variant="subtitle2">
                  Relationships (conf ≥ {edgeMinConfidence.toFixed(2)})
                </Typography>
              </AccordionSummary>
              <AccordionDetails>
                <Typography variant="caption" color="text.secondary" display="block">
                  inbound {filteredInbound.length} / outbound {filteredOutbound.length}
                </Typography>

                <Divider sx={{ my: 1 }} />

                <Typography variant="subtitle2">Inbound</Typography>
                <List dense disablePadding sx={{ mb: 1 }}>
                  {filteredInbound.slice(0, 80).map((e) => (
                    <ListItemButton key={e.id} sx={{ borderRadius: 1 }}>
                      <ListItemText
                        primary={
                          <Typography variant="body2" sx={{ fontFamily: "ui-monospace, monospace" }}>
                            {prettyEdgeLabel(e.type)} • conf {formatConfidence(e.confidence)}
                          </Typography>
                        }
                        secondary={
                          e.evidence ? (
                            <Typography variant="caption" color="text.secondary">
                              {e.evidence}
                            </Typography>
                          ) : null
                        }
                      />
                    </ListItemButton>
                  ))}
                  {!filteredInbound.length ? (
                    <Typography variant="caption" color="text.secondary" sx={{ px: 1 }}>
                      —
                    </Typography>
                  ) : null}
                </List>

                <Typography variant="subtitle2">Outbound</Typography>
                <List dense disablePadding>
                  {filteredOutbound.slice(0, 80).map((e) => (
                    <ListItemButton key={e.id} sx={{ borderRadius: 1 }}>
                      <ListItemText
                        primary={
                          <Typography variant="body2" sx={{ fontFamily: "ui-monospace, monospace" }}>
                            {prettyEdgeLabel(e.type)} • conf {formatConfidence(e.confidence)}
                          </Typography>
                        }
                        secondary={
                          e.evidence ? (
                            <Typography variant="caption" color="text.secondary">
                              {e.evidence}
                            </Typography>
                          ) : null
                        }
                      />
                    </ListItemButton>
                  ))}
                  {!filteredOutbound.length ? (
                    <Typography variant="caption" color="text.secondary" sx={{ px: 1 }}>
                      —
                    </Typography>
                  ) : null}
                </List>
              </AccordionDetails>
            </Accordion>

            {/* RAW */}
            <Accordion>
              <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                <Typography variant="subtitle2">Raw node</Typography>
              </AccordionSummary>
              <AccordionDetails>
                <KeyValueBlock obj={selected.node} maxHeight={320} />
              </AccordionDetails>
            </Accordion>

            {/* DEEP DIVE */}
            <Accordion>
              <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                <Typography variant="subtitle2">Deep dive</Typography>
              </AccordionSummary>
              <AccordionDetails>
                {!jobId || !nodeId ? (
                  <Typography variant="caption" color="text.secondary">
                    Missing jobId or nodeId.
                  </Typography>
                ) : (
                  <>
                    <Typography variant="caption" color="text.secondary" display="block">
                      node:{nodeId}
                    </Typography>

                    <Divider sx={{ my: 1 }} />

                    <Typography variant="subtitle2">resource.json</Typography>
                    {!nodeFiles.includes("resource.json") ? (
                      <Typography variant="caption" color="text.secondary">
                        Not listed in node.metadata.files.
                      </Typography>
                    ) : resourceLoading ? (
                      <Typography variant="caption" color="text.secondary">
                        Loading…
                      </Typography>
                    ) : resourceErr ? (
                      <Typography variant="caption" color="error">
                        {resourceErr}
                      </Typography>
                    ) : resourceJson ? (
                      <>
                        <Typography variant="caption" color="text.secondary" display="block">
                          scope {String(resourceJson.scope ?? "—")} • version {String(resourceJson.version ?? "—")}
                        </Typography>
                        <Typography variant="caption" color="text.secondary" display="block">
                          restricted {String(resourceJson.restricted ?? "—")} • overridable{" "}
                          {String(resourceJson.overridable ?? "—")}
                        </Typography>

                        <Divider sx={{ my: 1 }} />

                        <Typography variant="subtitle2">Attributes</Typography>
                        <KeyValueBlock obj={resourceJson.attributes ?? {}} maxHeight={220} />

                        {!!resourceClaimsFiles.length ? (
                          <>
                            <Divider sx={{ my: 1 }} />
                            <Typography variant="subtitle2">Files (from resource.json)</Typography>
                            <Typography
                              variant="caption"
                              sx={{ fontFamily: "ui-monospace, monospace", display: "block" }}
                              color="text.secondary"
                            >
                              {resourceClaimsFiles.join(", ")}
                            </Typography>
                          </>
                        ) : null}
                      </>
                    ) : (
                      <Typography variant="caption" color="text.secondary">
                        —
                      </Typography>
                    )}

                    <Divider sx={{ my: 1 }} />

                    <Typography variant="subtitle2">Files (from node.metadata.files)</Typography>

                    {deepDiveFiles.length ? (
                      <List dense disablePadding sx={{ mt: 0.5 }}>
                        {deepDiveFiles.map((f) => (
                          <ListItemButton
                            key={f}
                            selected={activeFile === f}
                            onClick={() => setActiveFile(f)}
                            sx={{ borderRadius: 1 }}
                          >
                            <ListItemText
                              primary={
                                <Typography variant="body2" sx={{ fontFamily: "ui-monospace, monospace" }}>
                                  {f}
                                </Typography>
                              }
                              secondary={
                                <Typography variant="caption" color="text.secondary">
                                  kind: {kindFor(nodeId, f)}
                                </Typography>
                              }
                            />
                          </ListItemButton>
                        ))}
                      </List>
                    ) : (
                      <Typography variant="caption" color="text.secondary">
                        No files listed for this node.
                      </Typography>
                    )}

                    {activeFile && activeKind ? (
                      <>
                        <Divider sx={{ my: 1 }} />
                        <Typography variant="subtitle2">Preview</Typography>
                        <ArtifactPreview jobId={jobId} kind={activeKind} file={activeFile} />
                      </>
                    ) : null}
                  </>
                )}
              </AccordionDetails>
            </Accordion>
          </>
        )}
      </Box>
    </Drawer>
  );
}
