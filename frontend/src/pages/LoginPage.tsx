import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Box,
  Button,
  Card,
  CardContent,
  TextField,
  Typography,
  InputAdornment,
  IconButton
} from "@mui/material";
import VisibilityIcon from "@mui/icons-material/Visibility";
import VisibilityOffIcon from "@mui/icons-material/VisibilityOff";
import { useSnackbar } from "notistack";
import { api } from "../api/client";

export default function LoginPage({ onLogin }: { onLogin: () => void }) {
  const [password, setPassword] = useState("");
  const [show, setShow] = useState(false);
  const [busy, setBusy] = useState(false);
  const { enqueueSnackbar } = useSnackbar();
  const nav = useNavigate();

  const submit = async () => {
    setBusy(true);
    try {
      await api.login(password);
      onLogin();
      nav("/tools/ignition/graph");
    } catch (e: any) {
      enqueueSnackbar(e.message || "Login failed", { variant: "error" });
    } finally {
      setBusy(false);
    }
  };

  return (
    <Box sx={{ height: "100vh", display: "flex", alignItems: "center", justifyContent: "center", p: 2 }}>
      <Card sx={{ width: 420 }}>
        <CardContent sx={{ display: "flex", flexDirection: "column", gap: 2 }}>
          <Typography variant="h6">Controls Workbench</Typography>
          <Typography variant="body2" color="text.secondary">
            Enter the app password to continue.
          </Typography>

          <TextField
            label="App Password"
            type={show ? "text" : "password"}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") submit(); }}
            InputProps={{
              endAdornment: (
                <InputAdornment position="end">
                  <IconButton onClick={() => setShow((v) => !v)} edge="end">
                    {show ? <VisibilityOffIcon /> : <VisibilityIcon />}
                  </IconButton>
                </InputAdornment>
              )
            }}
          />

          <Button variant="contained" disabled={!password || busy} onClick={submit}>
            {busy ? "Signing in..." : "Sign in"}
          </Button>
        </CardContent>
      </Card>
    </Box>
  );
}
