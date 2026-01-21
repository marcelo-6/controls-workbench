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
  IconButton,
  useTheme
} from "@mui/material";
import VisibilityIcon from "@mui/icons-material/Visibility";
import VisibilityOffIcon from "@mui/icons-material/VisibilityOff";
import { useSnackbar } from "notistack";
import { api } from "../api/client";

export default function LoginPage({ onLogin }: { onLogin: () => void }) {
  const [password, setPassword] = useState("");
  const [show, setShow] = useState(false);
  const [busy, setBusy] = useState(false);

  const theme = useTheme();
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
    <Box
      sx={{
        height: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        p: 2,
        backgroundColor: theme.palette.background.default
      }}
    >
      <Card
        elevation={0}
        sx={(theme) => ({
          width: 420,
          borderRadius: "12px",
          border: `1px solid ${theme.palette.divider}`,
          backgroundColor: theme.palette.background.paper,
        })}
      >
        <CardContent
          sx={{
            display: "flex",
            flexDirection: "column",
            gap: 2.5,
            p: 3
          }}
        >
          <Typography
            variant="h5"
            sx={(theme) => ({
              fontWeight: 600,
              color: theme.palette.text.primary
            })}
          >
            Controls Workbench
          </Typography>

          <Typography
            variant="body2"
            sx={(theme) => ({
              color: theme.palette.text.secondary
            })}
          >
            Enter the app password to continue.
          </Typography>

          <TextField
            label="App Password"
            type={show ? "text" : "password"}
            value={password}
            autoFocus
            onChange={(e) => setPassword(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && submit()}
            variant="outlined"
            fullWidth
            InputProps={{
              endAdornment: (
                <InputAdornment position="end">
                  <IconButton onClick={() => setShow((v) => !v)} edge="end">
                    {show ? <VisibilityOffIcon /> : <VisibilityIcon />}
                  </IconButton>
                </InputAdornment>
              )
            }}
            sx={(theme) => ({
              "& .MuiOutlinedInput-root": {
                borderRadius: "8px",
              }
            })}
          />

          <Button
            size="medium"
            variant="outlined"
            color="primary"
            disabled={!password || busy}
            onClick={submit}
            sx={(theme) => ({
              textTransform: "none",
              fontWeight: 600,
              borderRadius: 999,
              px: 2,
              py: 1,
              borderWidth: 2,
              backgroundColor: theme.palette.mode === "dark"
                ? "rgba(255,255,255,0.04)"
                : "transparent",
              ":hover": {
                backgroundColor: theme.palette.mode === "dark"
                  ? "rgba(255,255,255,0.08)"
                  : theme.palette.action.hover,
                borderColor: theme.palette.primary.main
              },
              ":disabled": {
                opacity: 0.5
              }
            })}
          >
            {busy ? "Signing in..." : "Sign in"}
          </Button>
        </CardContent>
      </Card>
    </Box>
  );
}