import React, { useEffect, useMemo, useRef, useState } from "react";
import { Box, CircularProgress, Typography } from "@mui/material";
import { alpha, useTheme } from "@mui/material/styles";
import { api } from "../api/client";
import * as echarts from "echarts";

type Props = {
  jobId: string;

  /**
   * Which backend artifact to fetch.
   * NOTE: treemap uses the same underlying data as echarts_tree.
   */
  kind: "echarts_tree" | "echarts_graph_full";

  /**
   * How to render the fetched data (tree artifact can render as "tree" OR "treemap")
   */
  view?: "tree" | "treemap" | "graph";
};

type UiTheme = {
  surface: string;
  surface2: string;
  fg: string;
  mutedFg: string;
  border: string;
  accent: string;
  accentStrong: string;
  tooltipBg: string;
  shadow: string;
};

function deriveUiTheme(theme: any): UiTheme {
  const mode = theme.palette.mode;
  const bg = theme.palette.background.default;
  const paper = theme.palette.background.paper;

  const fg = theme.palette.text.primary;
  const muted = theme.palette.text.secondary;

  const surface = alpha(paper, mode === "dark" ? 0.86 : 0.92);
  const surface2 = alpha(paper, mode === "dark" ? 0.72 : 0.98);

  const border = alpha(theme.palette.divider, mode === "dark" ? 0.75 : 0.9);

  const accent = theme.palette.primary.main;
  const accentStrong = mode === "dark" ? theme.palette.primary.light : theme.palette.primary.dark;

  const tooltipBg = alpha(bg, mode === "dark" ? 0.82 : 0.92);

  const shadow =
    mode === "dark"
      ? "0 10px 30px rgba(0,0,0,0.45)"
      : "0 10px 30px rgba(0,0,0,0.12)";

  return { surface, surface2, fg, mutedFg: muted, border, accent, accentStrong, tooltipBg, shadow };
}

function asArray<T>(x: T | T[] | null | undefined): T[] {
  if (!x) return [];
  return Array.isArray(x) ? x : [x];
}

/**
 * Tree -> Treemap data needs `value`.
 * We compute value as leaf-count by default (works well visually).
 */
type TreeNode = { name?: string; children?: TreeNode[]; [k: string]: any };
type TreemapNode = { name: string; value: number; children?: TreemapNode[]; [k: string]: any };

function computeLeafCount(n: TreeNode): number {
  const kids = n?.children ?? [];
  if (!kids.length) return 1;
  let sum = 0;
  for (const k of kids) sum += computeLeafCount(k);
  return sum;
}

function toTreemap(node: TreeNode): TreemapNode {
  const name = String(node?.name ?? "Unnamed");
  const kids = node?.children ?? [];
  if (!kids.length) {
    return { name, value: 1 };
  }
  const children = kids.map(toTreemap);
  const value = children.reduce((acc, c) => acc + (c.value ?? 0), 0) || computeLeafCount(node);
  return { name, value, children };
}

function buildTreeOption(treeData: any, ui: UiTheme) {
  const dataArr = asArray(treeData);

  return {
    backgroundColor: ui.surface,
    textStyle: { color: ui.fg },
    tooltip: {
      trigger: "item",
      triggerOn: "mousemove",
      backgroundColor: ui.tooltipBg,
      borderColor: ui.border,
      borderWidth: 1,
      textStyle: { color: ui.fg },
      extraCssText: `border-radius: 12px; padding: 8px 10px; box-shadow: ${ui.shadow};`,
    },
    series: [
      {
        type: "tree",
        data: dataArr,
        top: "6%",
        left: "18%",
        bottom: "6%",
        right: "18%",

        symbolSize: 10,
        lineStyle: { color: alpha(ui.mutedFg, 0.75), width: 1 },
        itemStyle: {
          color: ui.accent,
          borderColor: alpha(ui.accent, 0.35),
          borderWidth: 1,
        },
        label: {
          position: "left",
          verticalAlign: "middle",
          align: "right",
          fontSize: 12,
          color: ui.fg,
          overflow: "truncate",
          width: 180,
        },
        leaves: {
          label: {
            position: "right",
            verticalAlign: "middle",
            align: "left",
            color: ui.fg,
            overflow: "truncate",
            width: 200,
          },
        },
        emphasis: {
          focus: "descendant",
          itemStyle: { color: ui.accentStrong },
          lineStyle: { color: ui.accent, width: 2 },
        },
        expandAndCollapse: true,
        animationDuration: 450,
        animationDurationUpdate: 300,
      },
    ],
  };
}

function buildTreemapOption(treeData: any, ui: UiTheme) {
  const roots = asArray(treeData).map(toTreemap);

  // Stronger contrast than 0.05 / 0.08 (those are basically invisible in light mode)
  const fillL1 = alpha(ui.accent, 0.18);
  const fillL2 = alpha(ui.accent, 0.12);
  const fillL3 = alpha(ui.accent, 0.08);

  // Border that contrasts with both light/dark
  const border = alpha(ui.fg, 0.18);
  const borderStrong = alpha(ui.fg, 0.28);

  // Truncate helper for labels (echarts doesn't support `overflow: "truncate"` in label)
  const truncate = (s: any, n = 18) => {
    const t = String(s ?? "");
    return t.length > n ? `${t.slice(0, n - 1)}…` : t;
  };

  return {
    backgroundColor: ui.surface,
    textStyle: { color: ui.fg },

    tooltip: {
      trigger: "item",
      backgroundColor: ui.tooltipBg,
      borderColor: ui.border,
      borderWidth: 1,
      textStyle: { color: ui.fg },
      extraCssText: `border-radius: 12px; padding: 8px 10px; box-shadow: ${ui.shadow};`,
      formatter: (info: any) => {
        const name = info?.name ?? "—";
        const value = info?.value ?? "—";
        const path = (info?.treePathInfo ?? [])
          .map((p: any) => p?.name)
          .filter(Boolean)
          .join(" / ");
        return `
          <div style="display:flex;flex-direction:column;gap:4px;">
            <div style="font-weight:650;">${name}</div>
            <div style="opacity:.8;font-size:12px;">${path}</div>
            <div style="opacity:.9;font-size:12px;">size: <b>${value}</b></div>
          </div>
        `;
      },
    },

    series: [
      {
        type: "treemap",
        data: roots,

        roam: true,
        nodeClick: "zoomToNode",
        zoomToNodeRatio: 0.55,

        // Helps avoid "nothing visible" when values are tiny or heavily nested
        visibleMin: 1,
        leafDepth: 4,

        breadcrumb: {
          show: true,
          height: 22,
          emptyItemWidth: 18,
        //   itemStyle: { color: "transparent", borderColor: "transparent" },
        //   emphasis: { itemStyle: { color: alpha(ui.accent, 0.12) } },
          textStyle: { color: ui.mutedFg, fontSize: 12 },
        },

        // IMPORTANT: give a base fill + border at series level
        itemStyle: {
        //   color: fillL2,
        
          borderColor: border,
          borderWidth: 1,
          gapWidth: 2,
        },

        label: {
          show: true,
          color: ui.fg,
          fontSize: 12,
          fontWeight: 650,
          formatter: (p: any) => truncate(p?.name, 18),
        },

        upperLabel: {
          show: true,
          color: ui.fg,
          fontSize: 12,
          fontWeight: 700,
          formatter: (p: any) => truncate(p?.name, 22),
        },

        emphasis: {
          itemStyle: {
            borderColor: alpha(ui.accent, 0.25),
            borderWidth: 2,
          },
          label: { color: ui.fg },
        },

        // “shadcn-ish” levels: subtle but actually visible
        levels: [
          {
            // root
            itemStyle: {
            //   color: fillL1,
              borderColor: borderStrong,
              borderWidth: 1,
              gapWidth: 3,
            },
            upperLabel: { show: true },
          },
          {
            // level 1
            itemStyle: {
            //   color: fillL2,
              borderColor: border,
              borderWidth: 1,
              gapWidth: 2,
            },
          },
          {
            // level 2+
            itemStyle: {
              color: fillL3,
              borderColor: border,
              borderWidth: 1,
              gapWidth: 1,
            },
          },
        ],

        animationDuration: 350,
        animationDurationUpdate: 250,
      },
    ],
  };
}


function buildGraphOption(graphData: any, ui: UiTheme) {
  const nodes = graphData?.nodes ?? graphData?.data ?? [];
  const links = graphData?.links ?? graphData?.edges ?? [];
  const categories = graphData?.categories;

  return {
    tooltip: {
      trigger: "item",
      backgroundColor: ui.tooltipBg,
      borderColor: ui.border,
      borderWidth: 1,
      textStyle: { color: ui.fg },
      extraCssText: `border-radius: 12px; padding: 8px 10px; box-shadow: ${ui.shadow};`,
    },
    legend: categories
      ? [{ data: categories.map((c: any) => c.name), textStyle: { color: ui.mutedFg } }]
      : undefined,
    series: [
      {
        type: "graph",
        layout: "force",
        draggable: true,
        roam: true,
        data: nodes,
        links,
        categories,
        label: { show: false, color: ui.fg, fontSize: 12 },
        itemStyle: { borderColor: ui.border, borderWidth: 1 },
        lineStyle: { color: ui.mutedFg, opacity: 0.35, width: 1 },
        force: { repulsion: 200, gravity: 0.05, edgeLength: [50, 150], friction: 0.2 },
        scaleLimit: { min: 0.4, max: 2 },
        emphasis: {
          focus: "adjacency",
          label: { color: ui.fg },
          lineStyle: { opacity: 0.75, width: 2, color: ui.accent },
        },
        animation: true,
      },
    ],
  };
}

export default function EChartsArtifact({ jobId, kind, view }: Props) {
  const theme = useTheme();
  const ui = useMemo(() => deriveUiTheme(theme), [theme]);

  const ref = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<echarts.ECharts | null>(null);

  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");
  const [data, setData] = useState<any | null>(null);

  const effectiveView: "tree" | "treemap" | "graph" =
    view ?? (kind === "echarts_graph_full" ? "graph" : "tree");

  // If treemap view, still fetch echarts_tree data
  const effectiveKind: Props["kind"] =
    effectiveView === "treemap" ? "echarts_tree" : kind;

  useEffect(() => {
    let alive = true;

    async function run() {
      setErr("");
      setData(null);
      setLoading(true);

      try {
        const res = await api.getArtifactJson(jobId, effectiveKind);
        if (!alive) return;
        setData(res?.data ?? null); // ✅ envelope.data only
      } catch (e: any) {
        if (!alive) return;
        setErr(e.message || `Failed to load ${effectiveKind}`);
      } finally {
        if (!alive) return;
        setLoading(false);
      }
    }

    run();
    return () => {
      alive = false;
    };
  }, [jobId, effectiveKind]);

  const option = useMemo(() => {
    if (!data) return null;

    if (effectiveView === "treemap") return buildTreemapOption(data, ui);
    if (effectiveView === "tree") return buildTreeOption(data, ui);
    return buildGraphOption(data, ui);
  }, [data, effectiveView, ui]);

  useEffect(() => {
    if (!ref.current) return;

    if (!chartRef.current) {
      chartRef.current = echarts.init(ref.current, undefined, {
        renderer: "canvas",
        useDirtyRect: false,
      });
    }

    if (option) {
      chartRef.current.setOption(option, { notMerge: true, lazyUpdate: true });
    } else {
      chartRef.current.clear();
    }

    const onResize = () => chartRef.current?.resize();
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, [option]);

  useEffect(() => {
    return () => {
      chartRef.current?.dispose();
      chartRef.current = null;
    };
  }, []);

  const title =
    effectiveView === "treemap" ? "Treemap" : effectiveView === "tree" ? "Tree" : "Graph";

  return (
    <Box
      sx={{
        height: "100%",
        minHeight: 0,
        position: "relative",
        borderRadius: 2.5,
        boxShadow: ui.shadow,
      }}
    >
      <Box
        sx={{
          px: 1.5,
          py: 1,
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
        }}
      >
        <Typography variant="body2" sx={{ fontWeight: 650 }}>
          {title}
        </Typography>

        <Typography
          variant="caption"
          sx={{
            fontFamily: "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
            color: ui.mutedFg,
          }}
        >
          {effectiveKind} → {effectiveView}
        </Typography>
      </Box>

      <Box sx={{ position: "absolute", inset: 0, top: 44 }}>
        <Box ref={ref} sx={{ position: "absolute", inset: 0 }} />

        {(loading || err) && (
          <Box
            sx={{
              position: "absolute",
              inset: 0,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              pointerEvents: "none",
              backdropFilter: "blur(2px)",
            }}
          >
            <Box
              sx={{
                borderRadius: 2,
                px: 2,
                py: 1.5,
                boxShadow: ui.shadow,
                display: "flex",
                alignItems: "center",
                gap: 1.25,
                maxWidth: 520,
              }}
            >
              {loading ? <CircularProgress size={18} /> : null}
              <Box>
                <Typography variant="body2" sx={{ fontWeight: 600 }}>
                  {loading ? "Loading…" : "Error"}
                </Typography>
                <Typography variant="caption" sx={{ color: err ? "error.main" : ui.mutedFg }}>
                  {err ? err : `Fetching ${effectiveKind}`}
                </Typography>
              </Box>
            </Box>
          </Box>
        )}

        {!loading && !err && !data && (
          <Box sx={{ p: 2 }}>
            <Typography variant="body2" color="text.secondary">
              No data returned for {effectiveKind}.
            </Typography>
          </Box>
        )}
      </Box>
    </Box>
  );
}
