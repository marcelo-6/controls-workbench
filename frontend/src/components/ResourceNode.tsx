import React, { useMemo, useState } from "react";
import { Box, Chip, Typography, useTheme } from "@mui/material";
import ViewQuiltIcon from "@mui/icons-material/ViewQuilt";
import CodeIcon from "@mui/icons-material/Code";
import StorageIcon from "@mui/icons-material/Storage";
import TagIcon from "@mui/icons-material/Tag";
import HelpOutlineIcon from "@mui/icons-material/HelpOutline";
import ErrorOutlineIcon from "@mui/icons-material/ErrorOutline";
import AutoFixHighIcon from "@mui/icons-material/AutoFixHigh";
import { Handle, Position, type NodeProps } from "reactflow";

type NodeStatus = "live" | "missing" | "derived";

type NodeData = {
  // required
  label: string;

  // new contract fields (provided by GraphView)
  nodeType?: string; // GraphNode.type (e.g. "perspective.view")
  path?: string | null;
  status?: NodeStatus;
  tags?: string[];
  tooltip?: string | null;
  description?: string | null;

  // UI helpers
  thumbnailUrl?: string | null;

  // for debugging
  raw?: any;
};

function iconFor(nodeType?: string) {
  const k = (nodeType || "").toLowerCase();
  if (k.includes("perspective") || k.includes("view")) return <ViewQuiltIcon fontSize="small" />;
  if (k.includes("script") || k.includes("python")) return <CodeIcon fontSize="small" />;
  if (k.includes("query") || k.includes("sql")) return <StorageIcon fontSize="small" />;
  if (k.includes("tag")) return <TagIcon fontSize="small" />;
  return <HelpOutlineIcon fontSize="small" />;
}

function statusChip(status: NodeStatus | undefined) {
  if (!status || status === "live") return null;

  if (status === "missing") {
    return (
      <Chip
        size="small"
        variant="filled"
        color="error"
        icon={<ErrorOutlineIcon />}
        label="Missing"
        sx={{ height: 22, "& .MuiChip-label": { px: 0.75 } }}
      />
    );
  }

  // derived
  return (
    <Chip
      size="small"
      variant="outlined"
      color="warning"
      icon={<AutoFixHighIcon />}
      label="Derived"
      sx={{ height: 22, "& .MuiChip-label": { px: 0.75 } }}
    />
  );
}

export default function ResourceNode(props: NodeProps<NodeData>) {
  const theme = useTheme();
  const { data, selected } = props;

  const [thumbOk, setThumbOk] = useState(true);

  const nodeType = data.nodeType || "resource";
  const status = (data.status || "live") as NodeStatus;

  const mono =
    "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace";

  const topTag = useMemo(() => {
    // optional: show a single helpful tag if present (not standardized yet)
    const tags = data.tags || [];
    const section = tags.find((t) => String(t).toLowerCase().startsWith("section:"));
    return section || tags[0] || null;
  }, [data.tags]);

  return (
    <Box
      sx={{
        width: 280,
        borderRadius: 2,
        overflow: "hidden",

        border: "1px solid",
        borderColor: selected ? "primary.main" : "divider",

        bgcolor: "background.paper",
        color: "text.primary",

        boxShadow: selected
          ? `0 0 0 2px ${theme.palette.primary.main}33`
          : theme.palette.mode === "dark"
            ? "0 10px 30px rgba(0,0,0,0.45)"
            : "0 10px 30px rgba(0,0,0,0.15)",

        transition: "transform 120ms ease, box-shadow 120ms ease, border-color 120ms ease",
        "&:hover": {
          transform: "translateY(-1px)",
          borderColor: selected ? "primary.main" : "text.secondary"
        }
      }}
    >
      {/* Handles (invisible but required for edge connections) */}
      <Handle type="target" position={Position.Left} style={{ opacity: 0 }} />
      <Handle type="source" position={Position.Right} style={{ opacity: 0 }} />

      {data.thumbnailUrl && thumbOk ? (
        <Box
          component="img"
          src={data.thumbnailUrl}
          alt="thumbnail"
          onError={() => setThumbOk(false)}
          sx={{
            width: "100%",
            height: 64,
            objectFit: "cover",
            display: "block",
            borderBottom: "1px solid",
            borderColor: "divider"
          }}
        />
      ) : null}

      <Box sx={{ p: 1 }}>
        {/* Header row */}
        <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
          <Box sx={{ color: "text.secondary", display: "flex", alignItems: "center" }}>
            {iconFor(nodeType)}
          </Box>

          <Typography
            variant="subtitle2"
            sx={{
              fontWeight: 700,
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
              flex: 1
            }}
            title={data.tooltip || data.label}
          >
            {data.label}
          </Typography>

          {statusChip(status)}
        </Box>

        {/* Type + optional tag */}
        <Box sx={{ display: "flex", alignItems: "center", gap: 0.75, mt: 0.25, flexWrap: "wrap" }}>
          <Typography variant="caption" sx={{ color: "text.secondary" }}>
            {nodeType}
          </Typography>

          {topTag ? (
            <Chip
              size="small"
              variant="outlined"
              label={topTag}
              sx={{
                height: 20,
                "& .MuiChip-label": { px: 0.5, fontSize: 11 }
              }}
            />
          ) : null}
        </Box>

        {/* Path */}
        {data.path ? (
          <Typography
            variant="caption"
            sx={{
              color: "text.secondary",
              display: "block",
              mt: 0.4,
              fontFamily: mono,
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap"
            }}
            title={data.path || undefined}
          >
            {data.path}
          </Typography>
        ) : null}

        {/* (Optional) small description line */}
        {data.description ? (
          <Typography
            variant="caption"
            sx={{
              color: "text.secondary",
              display: "block",
              mt: 0.4,
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap"
            }}
            title={data.description || undefined}
          >
            {data.description}
          </Typography>
        ) : null}

        {/* Metrics removed in Phase 1 (not in new backend contract) */}
      </Box>
    </Box>
  );
}
