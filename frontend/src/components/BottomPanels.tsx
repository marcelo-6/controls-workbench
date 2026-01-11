import React, { useEffect, useMemo, useState } from "react";
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
  ToggleButton
} from "@mui/material";
import ExpandLessIcon from "@mui/icons-material/ExpandLess";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import DownloadIcon from "@mui/icons-material/Download";
import RefreshIcon from "@mui/icons-material/Refresh";
import { api } from "../api/client";
import { useOutput } from "../state/output";
import { useSnackbar } from "notistack";

function LinesBox({ lines }: { lines: string[] }) {
  return (
    <Box
      sx={{
        fontFamily: "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
        fontSize: 12,
        whiteSpace: "pre",
        overflow: "auto",
        height: "100%",
        p: 1
      }}
    >
      {lines.length ? lines.join("\n") : "—"}
    </Box>
  );
}

export default function BottomPanels() {
  const { currentJobId, lines: outputLines, clear } = useOutput();
  const [expanded, setExpanded] = useState(false);

  const [logName, setLogName] = useState<"api" | "worker">("api");
  const [latestLog, setLatestLog] = useState<string>("—");
  const [logDialogOpen, setLogDialogOpen] = useState(false);
  const [logTail, setLogTail] = useState<string[]>([]);
  const { enqueueSnackbar } = useSnackbar();

  // useEffect(() => {
  //   let cancelled = false;
  //   const tick = async () => {
  //     try {
  //       const res = await api.logLatest(logName);
  //       if (!cancelled) setLatestLog(res.lines?.[0] ?? "—");
  //     } catch {
  //       if (!cancelled) setLatestLog("—");
  //     }
  //   };
  //   tick();
  //   const id = setInterval(tick, 2500);
  //   return () => {
  //     cancelled = true;
  //     clearInterval(id);
  //   };
  // }, [logName]);

  const height = expanded ? 360 : 100;

  const refreshLogTail = async () => {
    try {
      const res = await api.logTail(logName, 4000);
      setLogTail(res.lines || []);
    } catch (e: any) {
      enqueueSnackbar(e.message || "Failed to load log tail", { variant: "error" });
    }
  };

  const downloadLogs = async () => {
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
  };

  return (
    <>
      <Paper
        elevation={4}
        sx={{
          height,
          display: "grid",
          zIndex: (theme) => theme.zIndex.modal + 1, // ensures it's above dialogs, drawers, etc.
          gridTemplateColumns: "1fr 1px 1fr",
          borderTop: 1,
          borderColor: "divider"
        }}
      >
        {/* Output (left) */}
        <Box sx={{ display: "flex", flexDirection: "column", minWidth: 0 }}>
          <Box sx={{ display: "flex", alignItems: "center", px: 1, py: 0.5, gap: 1 }}>
            <Typography variant="subtitle2" sx={{ flex: 1 }}>
              Output {currentJobId ? `• job ${currentJobId}` : ""}
            </Typography>
            <Button size="small" onClick={clear}>Clear</Button>
            <IconButton size="small" onClick={() => setExpanded((v) => !v)}>
              {expanded ? <ExpandMoreIcon /> : <ExpandLessIcon />}
            </IconButton>
          </Box>
          <Divider />
          <Box sx={{ flex: 1, minHeight: 0 }}>
            <LinesBox lines={outputLines.slice(-5000)} />
          </Box>
        </Box>

        <Divider orientation="vertical" flexItem />

        {/* Logs (right) */}
        <Box sx={{ display: "flex", flexDirection: "column", minWidth: 0 }}>
          <Box sx={{ display: "flex", alignItems: "center", px: 1, py: 0.5, gap: 1 }}>
            <Typography variant="subtitle2" sx={{ flex: 1 }}>
              Logs • latest
            </Typography>

            <ToggleButtonGroup
              size="small"
              exclusive
              value={logName}
              onChange={(_, v) => v && setLogName(v)}
            >
              <ToggleButton value="api">API</ToggleButton>
              <ToggleButton value="worker">Worker</ToggleButton>
            </ToggleButtonGroup>

            <Button size="small" onClick={() => { setLogDialogOpen(true); refreshLogTail(); }}>
              Open
            </Button>

            <IconButton size="small" onClick={downloadLogs}>
              <DownloadIcon />
            </IconButton>
          </Box>
          <Divider />
          <Box sx={{ flex: 1, minHeight: 0 }}>
            <LinesBox lines={[latestLog]} />
          </Box>
        </Box>
      </Paper>

      <Dialog open={logDialogOpen} onClose={() => setLogDialogOpen(false)} fullWidth maxWidth="lg">
        <DialogTitle>Log tail ({logName})</DialogTitle>
        <DialogContent dividers sx={{ height: 520 }}>
          <LinesBox lines={logTail} />
        </DialogContent>
        <DialogActions>
          <Button startIcon={<RefreshIcon />} onClick={refreshLogTail}>Refresh</Button>
          <Button startIcon={<DownloadIcon />} onClick={downloadLogs}>Download logs.zip</Button>
          <Button onClick={() => setLogDialogOpen(false)}>Close</Button>
        </DialogActions>
      </Dialog>
    </>
  );
}
