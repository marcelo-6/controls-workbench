import dagre from "@dagrejs/dagre";
import type { Edge, Node } from "reactflow";

// These are approximate sizes for our custom nodes.
// Dagre uses them to calculate spacing.
const NODE_WIDTH = 280;
const NODE_HEIGHT = 120;

export function layoutDagre(nodes: Node[], edges: Edge[], direction: "LR" | "TB" = "LR"): { nodes: Node[]; edges: Edge[] } {
  const g = new dagre.graphlib.Graph();
  g.setDefaultEdgeLabel(() => ({}));
  g.setGraph({ rankdir: direction });

  nodes.forEach((n) => g.setNode(n.id, { width: NODE_WIDTH, height: NODE_HEIGHT }));
  edges.forEach((e) => g.setEdge(e.source, e.target));

  dagre.layout(g);

  const nextNodes = nodes.map((n) => {
    const p = g.node(n.id);
    return {
      ...n,
      position: { x: p.x - NODE_WIDTH / 2, y: p.y - NODE_HEIGHT / 2 }
    };
  });

  return { nodes: nextNodes, edges };
}
