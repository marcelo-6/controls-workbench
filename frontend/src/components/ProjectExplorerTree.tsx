import React, { useMemo, useState } from "react";
import {
  Box,
  Collapse,
  IconButton,
  List,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  TextField,
  Typography
} from "@mui/material";
import FolderIcon from "@mui/icons-material/Folder";
import FolderOpenIcon from "@mui/icons-material/FolderOpen";
import ExpandLessIcon from "@mui/icons-material/ExpandLess";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import ViewQuiltIcon from "@mui/icons-material/ViewQuilt";
import CodeIcon from "@mui/icons-material/Code";
import StorageIcon from "@mui/icons-material/Storage";
import TagIcon from "@mui/icons-material/Tag";
import HelpOutlineIcon from "@mui/icons-material/HelpOutline";

type TreeNode = {
  id: string;
  label: string;
  kind: string;
  children?: TreeNode[];
  element_id?: string;
  path?: string;
  thumbnail_path?: string;
};

function iconForKind(kind: string, expanded: boolean) {
  const k = (kind || "").toLowerCase();
  if (k === "folder" || k === "category" || k === "root") {
    return expanded ? <FolderOpenIcon fontSize="small" /> : <FolderIcon fontSize="small" />;
  }
  if (k.includes("perspective") || k.includes("view")) return <ViewQuiltIcon fontSize="small" />;
  if (k.includes("script") || k.includes("python")) return <CodeIcon fontSize="small" />;
  if (k.includes("query")) return <StorageIcon fontSize="small" />;
  if (k.includes("tag")) return <TagIcon fontSize="small" />;
  return <HelpOutlineIcon fontSize="small" />;
}

function filterTree(node: TreeNode, qLower: string): TreeNode | null {
  if (!qLower) return node;
  const hay = `${node.label} ${node.path || ""} ${node.kind}`.toLowerCase();
  const selfMatch = hay.includes(qLower);
  const children = node.children || [];
  const kept = children
    .map((c) => filterTree(c, qLower))
    .filter((x): x is TreeNode => Boolean(x));
  if (selfMatch || kept.length) {
    return { ...node, children: kept };
  }
  return null;
}

function collectExpandableIds(node: TreeNode, out: Set<string>) {
  if (node.children && node.children.length) {
    out.add(node.id);
    for (const c of node.children) collectExpandableIds(c, out);
  }
}

type Props = {
  tree: TreeNode;
  selectedId: string | null;
  onSelect: (elementId: string) => void;
};

export default function ProjectExplorerTree({ tree, selectedId, onSelect }: Props) {
  const [q, setQ] = useState("");
  const qLower = q.trim().toLowerCase();

  const filteredTree = useMemo(
    () => filterTree(tree, qLower) || { ...tree, children: [] },
    [tree, qLower]
  );

  const defaultExpanded = useMemo(() => {
    const s = new Set<string>();
    // Expand root + categories by default for discoverability
    s.add(filteredTree.id);
    for (const ch of filteredTree.children || []) s.add(ch.id);
    return s;
  }, [filteredTree]);

  const [expanded, setExpanded] = useState<Set<string>>(defaultExpanded);

  // If the filter changes a lot, keep expanded sane by ensuring root/categories are open
  React.useEffect(() => {
    setExpanded((prev) => {
      const next = new Set(prev);
      next.add(filteredTree.id);
      for (const ch of filteredTree.children || []) next.add(ch.id);
      return next;
    });
  }, [filteredTree.id]);

  const toggle = (id: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const expandAll = () => {
    const all = new Set<string>();
    collectExpandableIds(filteredTree, all);
    setExpanded(all);
  };

  const collapseAll = () => {
    setExpanded(new Set([filteredTree.id]));
  };

  const renderNode = (node: TreeNode, depth = 0) => {
    const hasChildren = Boolean(node.children && node.children.length);
    const isExpanded = expanded.has(node.id);
    const isLeaf = !hasChildren && node.kind !== "folder" && node.kind !== "category" && node.kind !== "root";
    const elementId = node.element_id || node.id;

    return (
      <React.Fragment key={node.id}>
        <ListItemButton
          dense
          selected={isLeaf && selectedId === elementId}
          onClick={() => {
            if (hasChildren) {
              toggle(node.id);
            } else {
              onSelect(elementId);
            }
          }}
          sx={{ pl: 1 + depth * 1.5 }}
        >
          <ListItemIcon sx={{ minWidth: 34, color: "text.secondary" }}>
            {iconForKind(node.kind, isExpanded)}
          </ListItemIcon>
          <ListItemText
            primary={node.label}
            secondary={depth <= 1 ? node.kind : undefined}
            primaryTypographyProps={{ noWrap: true, fontSize: 13 }}
            secondaryTypographyProps={{ noWrap: true, fontSize: 11 }}
          />
          {hasChildren ? (
            isExpanded ? <ExpandLessIcon fontSize="small" /> : <ExpandMoreIcon fontSize="small" />
          ) : null}
        </ListItemButton>

        {hasChildren ? (
          <Collapse in={isExpanded} timeout="auto" unmountOnExit>
            <List dense disablePadding>
              {(node.children || []).map((c) => renderNode(c, depth + 1))}
            </List>
          </Collapse>
        ) : null}
      </React.Fragment>
    );
  };

  return (
    <Box sx={{ height: "100%", display: "flex", flexDirection: "column", minHeight: 0}}>
      <Box sx={{ p: 1, display: "flex", flexDirection: "column", gap: 1, minHeight: 0}}>
        <Typography variant="subtitle2">Project explorer</Typography>
        <TextField
          size="small"
          placeholder="Filter (view/script/tag...)"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
        <Box sx={{ display: "flex", gap: 1 }}>
          <IconButton size="small" onClick={expandAll} title="Expand all">
            <ExpandMoreIcon fontSize="small" />
          </IconButton>
          <IconButton size="small" onClick={collapseAll} title="Collapse all">
            <ExpandLessIcon fontSize="small" />
          </IconButton>
        </Box>
      </Box>

      <Box sx={{ flex: 1, minHeight: 0, overflow: "auto" }}>
        <List dense disablePadding sx={{ minHeight: 0, maxHeight: 200 }}>
          {renderNode(filteredTree, 0)}
        </List>
      </Box>
    </Box>
  );
}
