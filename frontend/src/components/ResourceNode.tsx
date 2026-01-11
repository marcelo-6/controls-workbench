import React from "react";
import { Box, Typography } from "@mui/material";
import ViewQuiltIcon from "@mui/icons-material/ViewQuilt";
import CodeIcon from "@mui/icons-material/Code";
import StorageIcon from "@mui/icons-material/Storage";
import TagIcon from "@mui/icons-material/Tag";
import HelpOutlineIcon from "@mui/icons-material/HelpOutline";
import { Handle, Position, type NodeProps } from "reactflow";

type NodeData = {
  label: string;
  kind?: string;
  path?: string;
  thumbnailUrl?: string | null;
  metrics?: { fan_in?: number; fan_out?: number };
  raw?: any;
};

function iconFor(kind?: string) {
  const k = (kind || "").toLowerCase();
  if (k.includes("perspective") || k.includes("view")) return <ViewQuiltIcon fontSize="small" />;
  if (k.includes("script") || k.includes("python")) return <CodeIcon fontSize="small" />;
  if (k.includes("query")) return <StorageIcon fontSize="small" />;
  if (k.includes("tag")) return <TagIcon fontSize="small" />;
  return <HelpOutlineIcon fontSize="small" />;
}

export default function ResourceNode(props: NodeProps<NodeData>) {
  const { data, selected } = props;
  const kind = data.kind || "resource";
  const fin = data.metrics?.fan_in ?? 0;
  const fout = data.metrics?.fan_out ?? 0;

  return (
    <Box
      sx={{
        width: 280,
        borderRadius: 2,
        border: "1px solid var(--rf-border)",
        background: "var(--rf-surface)",
        color: "var(--rf-text)",
        boxShadow: selected ? "0 0 0 2px rgba(125, 211, 252, 0.35)" : "0 10px 30px rgba(0,0,0,0.25)",
        overflow: "hidden",
        backdropFilter: "blur(8px)",
      }}
    >
      {/* Handles */}
      <Handle type="target" position={Position.Left} style={{ opacity: 0 }} />
      <Handle type="source" position={Position.Right} style={{ opacity: 0 }} />

      {data.thumbnailUrl ? (
        <Box
          component="img"
          src={data.thumbnailUrl}
          alt="thumbnail"
          sx={{ width: "100%", height: 64, objectFit: "cover", display: "block" }}
        />
      ) : null}

      <Box sx={{ p: 1 }}>
        <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
          <Box sx={{ color: "var(--rf-text-muted)", display: "flex", alignItems: "center" }}>
            {iconFor(kind)}
          </Box>
          <Typography
            variant="subtitle2"
            sx={{
              fontWeight: 600,
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
              flex: 1
            }}
          >
            {data.label}
          </Typography>
        </Box>

        <Typography variant="caption" sx={{ color: "var(--rf-text-muted)", display: "block" }}>
          {kind}
        </Typography>

        {data.path ? (
          <Typography
            variant="caption"
            sx={{
              color: "var(--rf-text-muted)",
              display: "block",
              mt: 0.25,
              fontFamily: "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap"
            }}
          >
            {data.path}
          </Typography>
        ) : null}

        <Box sx={{ display: "flex", gap: 1, mt: 0.75 }}>
          <Typography variant="caption" sx={{ color: "var(--rf-text-muted)" }}>
            in {fin}
          </Typography>
          <Typography variant="caption" sx={{ color: "var(--rf-text-muted)" }}>
            out {fout}
          </Typography>
        </Box>
      </Box>
    </Box>
  );
}
