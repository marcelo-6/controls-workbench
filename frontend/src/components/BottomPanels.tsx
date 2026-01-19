import React, { useState, useMemo } from "react";
import {
  Box,
  Divider,
  IconButton,
  Paper,
  Typography,
  Button,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  ToggleButtonGroup,
  ToggleButton,
  Tooltip,
  TextField,
  InputAdornment,
  Slide,
} from "@mui/material";

import ExpandLessIcon from "@mui/icons-material/ExpandLess";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import DownloadIcon from "@mui/icons-material/Download";
import RefreshIcon from "@mui/icons-material/Refresh";
import SearchIcon from "@mui/icons-material/Search";
import OpenInNewIcon from "@mui/icons-material/OpenInNew";
import CloseIcon from "@mui/icons-material/Close";
import VisibilityOffIcon from "@mui/icons-material/VisibilityOff";
import VisibilityIcon from "@mui/icons-material/Visibility";

import { api } from "../api/client";
import { useOutput } from "../state/output";
import { useSnackbar } from "notistack";

//
// ------------------------------------------------------------
// LOG ENTRY FORMATTER
// ------------------------------------------------------------
//

function formatLogEntry(entry: {
  ts: string;
  level: string;
  message: string;
  kind: string;
  payload?: any;
}) {
  const ts = new Date(entry.ts).toISOString();
  const lvl = entry.level.toUpperCase().padEnd(5);
  const kind = entry.kind;
  const msg = entry.message;
  return `[${ts}] [${lvl}] [${kind}] ${msg}`;
}

//
// ------------------------------------------------------------
// COLORIZER
// ------------------------------------------------------------
//

function colorize(line: any): JSX.Element {
  if (typeof line !== "string") return <span>{String(line)}</span>;

  try {
    if (/error/i.test(line)) return <span style={{ color: "#ff5370" }}>{line}</span>;
    if (/warn/i.test(line)) return <span style={{ color: "#ffcb6b" }}>{line}</span>;
    if (/info/i.test(line)) return <span style={{ color: "#82aaff" }}>{line}</span>;
    if (/debug/i.test(line)) return <span style={{ color: "#c792ea" }}>{line}</span>;
  } catch {
    return <span>{line}</span>;
  }

  return <span>{line}</span>;
}

function LinesBox({ lines }: { lines: string[] }) {
  return (
    <Box
      sx={{
        fontFamily: "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
        fontSize: 12,
        whiteSpace: "pre",
        overflow: "auto",
        height: "100%",
        p: 1.5,
      }}
    >
      {lines.length ? lines.map((l, i) => <div key={i}>{colorize(l)}</div>) : "—"}
    </Box>
  );
}

//
// ------------------------------------------------------------
// MAIN COMPONENT
// ------------------------------------------------------------
//

export default function BottomPanels() {
  const { currentJobId, lines: outputLines, clear } = useOutput();
  const { enqueueSnackbar } = useSnackbar();

  const [expanded, setExpanded] = useState(false);
  const [hidden, setHidden] = useState(false);

  const [popout, setPopout] = useState(false);

  const [logName, setLogName] = useState<"api" | "worker">("api");
  const [latestLog, setLatestLog] = useState<string>("—");
  const [logDialogOpen, setLogDialogOpen] = useState(false);
  const [logTail, setLogTail] = useState<string[]>([]);

  const [search, setSearch] = useState("");
  const [regexMode, setRegexMode] = useState(false);

  const height = expanded ? 360 : 110;

  //
  // ------------------------------------------------------------
  // UPDATED: Fetch log tail (new backend format)
  // ------------------------------------------------------------
  //

  const refreshLogTail = async () => {
    try {
      const res = await api.logTail(logName, 4000);

      const raw = res?.data?.lines ?? [];
      const formatted = raw.map(formatLogEntry);

      setLogTail(formatted);

      if (formatted.length) {
        setLatestLog(formatted.at(-1)!);
      }
    } catch (e: any) {
      enqueueSnackbar(e.message || "Failed to load log tail", { variant: "error" });
    }
  };

  //
  // ------------------------------------------------------------
  // FILTER OUTPUT
  // ------------------------------------------------------------
  //

  const filteredOutput = useMemo(() => {
    if (!search) return outputLines.slice(-5000);

    try {
      if (regexMode) {
        const re = new RegExp(search, "i");
        return outputLines.filter((l) => re.test(l));
      }
      return outputLines.filter((l) =>
        l.toLowerCase().includes(search.toLowerCase())
      );
    } catch {
      return outputLines;
    }
  }, [outputLines, search, regexMode]);

  //
  // ------------------------------------------------------------
  // PANEL CONTENT
  // ------------------------------------------------------------
  //

  const panelContent = (
    <Box sx={{ display: "grid", gridTemplateColumns: "1fr 1px 1fr", height: "100%" }}>
      {/* ---------------- LEFT: OUTPUT ---------------- */}
      <Box sx={{ display: "flex", flexDirection: "column", minWidth: 0 }}>
        <Box
          sx={{
            display: "flex",
            alignItems: "center",
            px: 1.5,
            py: 0.75,
            gap: 1,
            bgcolor: "background.default",
            borderBottom: 1,
            borderColor: "divider",
          }}
        >
          <Typography variant="subtitle2" sx={{ flex: 1, fontWeight: 600 }}>
            Output {currentJobId ? `- job ${currentJobId.slice(0, 4)}…${currentJobId.slice(-4)}` : ""} 
          </Typography>

          <Tooltip title="Search output">
            <TextField
              size="small"
              placeholder="Search…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              sx={{ width: 160 }}
              InputProps={{
                startAdornment: (
                  <InputAdornment position="start">
                    <SearchIcon fontSize="small" />
                  </InputAdornment>
                ),
              }}
            />
          </Tooltip>

          <Tooltip title="Toggle regex mode">
            <ToggleButton
              size="small"
              value="regex"
              selected={regexMode}
              onChange={() => setRegexMode((v) => !v)}
            >
              .*
            </ToggleButton>
          </Tooltip>

          <Tooltip title="Clear output">
            <Button size="small" onClick={clear} sx={{ textTransform: "none" }}>
              Clear
            </Button>
          </Tooltip>

          <Tooltip title={expanded ? "Collapse panel" : "Expand panel"}>
            <IconButton size="small" onClick={() => setExpanded((v) => !v)}>
              {expanded ? <ExpandMoreIcon /> : <ExpandLessIcon />}
            </IconButton>
          </Tooltip>

          <Tooltip title="Pop out into separate window">
            <IconButton size="small" onClick={() => setPopout(true)}>
              <OpenInNewIcon />
            </IconButton>
          </Tooltip>

          <Tooltip title={hidden ? "Show panel" : "Hide panel"}>
            <IconButton size="small" onClick={() => setHidden((v) => !v)}>
              {hidden ? <VisibilityIcon /> : <VisibilityOffIcon />}
            </IconButton>
          </Tooltip>
        </Box>

        <Box sx={{ flex: 1, minHeight: 0 }}>
          <LinesBox lines={filteredOutput} />
        </Box>
      </Box>

      <Divider orientation="vertical" flexItem />

      {/* ---------------- RIGHT: LOGS ---------------- */}
      <Box sx={{ display: "flex", flexDirection: "column", minWidth: 0 }}>
        <Box
          sx={{
            display: "flex",
            alignItems: "center",
            px: 1.5,
            py: 0.75,
            gap: 1,
            bgcolor: "background.default",
            borderBottom: 1,
            borderColor: "divider",
          }}
        >
          <Typography variant="subtitle2" sx={{ flex: 1, fontWeight: 600 }}>
            Logs • latest
          </Typography>

          <Tooltip title="Select log source">
            <ToggleButtonGroup
              size="small"
              exclusive
              value={logName}
              onChange={(_, v) => v && setLogName(v)}
            >
              <ToggleButton value="api">API</ToggleButton>
              <ToggleButton value="worker">Worker</ToggleButton>
            </ToggleButtonGroup>
          </Tooltip>

          <Tooltip title="Open full log viewer">
            <Button
              size="small"
              onClick={() => {
                setLogDialogOpen(true);
                refreshLogTail();
              }}
              sx={{ textTransform: "none" }}
            >
              Open
            </Button>
          </Tooltip>

          <Tooltip title="Download logs.zip">
            <IconButton size="small" onClick={async () => {
              try {
                const res = await fetch("/api/logs/download", { credentials: "include" });
                if (!res.ok) throw new Error("Failed to download logs");

                const blob = await res.blob();
                const url = URL.createObjectURL(blob);
                const a = document.createElement("a");
                a.href = url;
                a.download = "logs.zip";
                a.click();
                URL.revokeObjectURL(url);
              } catch (e: any) {
                enqueueSnackbar(e.message || "Failed to download logs", { variant: "error" });
              }
            }}>
              <DownloadIcon />
            </IconButton>
          </Tooltip>
        </Box>

        <Box sx={{ flex: 1, minHeight: 0 }}>
          <LinesBox lines={[latestLog]} />
        </Box>
      </Box>
    </Box>
  );

  //
  // ------------------------------------------------------------
  // RENDER
  // ------------------------------------------------------------
  //

  return (
    <>
      {/* POP-OUT MODE */}
      {popout && (
        <Dialog
          open
          fullWidth
          maxWidth="xl"
          onClose={() => setPopout(false)}
          PaperProps={{
            sx: { height: "80vh", display: "flex", flexDirection: "column" },
          }}
        >
          <DialogTitle sx={{ display: "flex", alignItems: "center" }}>
            Console Output
            <Box sx={{ flex: 1 }} />
            <Tooltip title="Close pop-out">
              <IconButton onClick={() => setPopout(false)}>
                <CloseIcon />
              </IconButton>
            </Tooltip>
          </DialogTitle>

          <DialogContent dividers sx={{ p: 0 }}>
            {panelContent}
          </DialogContent>
        </Dialog>
      )}

      {/* MAIN PANEL */}
      <Slide direction="up" in={!hidden} mountOnEnter unmountOnExit>
        <Paper
          elevation={6}
          sx={{
            height,
            display: "flex",
            flexDirection: "column",
            borderTop: 1,
            borderColor: "divider",
            transition: "height 0.25s ease",
          }}
        >
          {panelContent}
        </Paper>
      </Slide>

      {/* LOG DIALOG */}
      <Dialog open={logDialogOpen} onClose={() => setLogDialogOpen(false)} fullWidth maxWidth="lg">
        <DialogTitle sx={{ fontWeight: 600 }}>Log tail ({logName})</DialogTitle>

        <DialogContent dividers sx={{ height: 520, p: 0 }}>
          <LinesBox lines={logTail} />
        </DialogContent>

        <DialogActions sx={{ px: 2, py: 1 }}>
          <Button startIcon={<RefreshIcon />} onClick={refreshLogTail}>
            Refresh
          </Button>
          <Button startIcon={<DownloadIcon />} onClick={() => {}}>
            Download logs.zip
          </Button>
          <Button onClick={() => setLogDialogOpen(false)}>Close</Button>
        </DialogActions>
      </Dialog>
    </>
  );
}