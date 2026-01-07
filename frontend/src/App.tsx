import React, { useEffect, useState } from "react";
import { Routes, Route, Navigate, useLocation } from "react-router-dom";
import { CircularProgress, Box } from "@mui/material";
import { useSnackbar } from "notistack";

import { api } from "./api/client";
import Shell from "./components/Shell";
import LoginPage from "./pages/LoginPage";
import IgnitionGraphPage from "./pages/IgnitionGraphPage";

export default function App() {
  const [ready, setReady] = useState(false);
  const [authed, setAuthed] = useState(false);
  const location = useLocation();
  const { enqueueSnackbar } = useSnackbar();

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const me = await api.me();
        if (!cancelled) setAuthed(Boolean(me.ok));
      } catch (e: any) {
        if (!cancelled) setAuthed(false);
      } finally {
        if (!cancelled) setReady(true);
      }
    })();
    return () => { cancelled = true; };
  }, [location.pathname]);

  if (!ready) {
    return (
      <Box sx={{ height: "100vh", display: "flex", alignItems: "center", justifyContent: "center" }}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Routes>
      <Route path="/login" element={<LoginPage onLogin={() => { setAuthed(true); enqueueSnackbar("Logged in", { variant: "success" }); }} />} />
      <Route
        path="/*"
        element={
          authed ? (
            <Shell onLogout={async () => { await api.logout(); setAuthed(false); enqueueSnackbar("Logged out", { variant: "info" }); }} />
          ) : (
            <Navigate to="/login" replace />
          )
        }
      />
    </Routes>
  );
}
