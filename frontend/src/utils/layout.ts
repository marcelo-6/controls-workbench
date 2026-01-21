// src/utils/layout.ts
import dagre from "@dagrejs/dagre";
import type { Edge, Node } from "reactflow";

export type DagreLayoutOptions = {
  direction?: "LR" | "RL" | "TB" | "BT";
  nodeSep?: number;   // spacing between nodes in same rank
  rankSep?: number;   // spacing between ranks
  marginX?: number;
  marginY?: number;
  ranker?: "network-simplex" | "tight-tree" | "longest-path";
  align?: "UL" | "UR" | "DL" | "DR";
  defaultNodeWidth?: number;
  defaultNodeHeight?: number;
};

const DEFAULTS: Required<DagreLayoutOptions> = {
  direction: "LR",
  nodeSep: 60,
  rankSep: 110,
  marginX: 40,
  marginY: 40,
  ranker: "network-simplex",
  align: "UL",
  defaultNodeWidth: 280,
  defaultNodeHeight: 90,
};

function getNodeSize(n: Node, opts: Required<DagreLayoutOptions>) {
  // ReactFlow nodes often don't have width/height until measured.
  // We can use style.width, or fall back to defaults.
  const w =
    (typeof (n.style as any)?.width === "number" ? (n.style as any).width : undefined) ??
    (typeof (n as any).width === "number" ? (n as any).width : undefined) ??
    opts.defaultNodeWidth;

  const h =
    (typeof (n.style as any)?.height === "number" ? (n.style as any).height : undefined) ??
    (typeof (n as any).height === "number" ? (n as any).height : undefined) ??
    opts.defaultNodeHeight;

  return { width: w, height: h };
}

export function layoutDagre(
  nodes: Node[],
  edges: Edge[],
  options?: DagreLayoutOptions
): { nodes: Node[]; edges: Edge[] } {
  const o = { ...DEFAULTS, ...(options ?? {}) };

  const g = new dagre.graphlib.Graph();
  g.setDefaultEdgeLabel(() => ({}));

  g.setGraph({
    rankdir: o.direction,
    nodesep: o.nodeSep,
    ranksep: o.rankSep,
    marginx: o.marginX,
    marginy: o.marginY,
    ranker: o.ranker,
    align: o.align,
  });

  // nodes
  for (const n of nodes) {
    const { width, height } = getNodeSize(n, o);
    g.setNode(n.id, { width, height });
  }

  // edges
  for (const e of edges) {
    // dagre expects edges by node id
    g.setEdge(e.source, e.target);
  }

  dagre.layout(g);

  const laidNodes: Node[] = nodes.map((n) => {
    const p = g.node(n.id);
    if (!p) return n;

    const { width, height } = getNodeSize(n, o);

    // dagre gives center positions; ReactFlow wants top-left
    const x = p.x - width / 2;
    const y = p.y - height / 2;

    return { ...n, position: { x, y } };
  });

  return { nodes: laidNodes, edges };
}
