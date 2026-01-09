import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { SnackbarProvider } from "notistack";
import { CssBaseline, ThemeProvider, createTheme } from "@mui/material";

import App from "./App";
import "reactflow/dist/style.css";

const theme = createTheme({
  palette: { mode: "dark" },
  shape: { borderRadius: 12 }
});

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <ThemeProvider theme={theme}>
        <CssBaseline />
          <SnackbarProvider
            maxSnack={4}
            preventDuplicate
            dense
            anchorOrigin={{ vertical: "top", horizontal: "right" }}
            autoHideDuration={3000}
            ComponentsProps={{
              default: {
                sx: {
                  borderRadius: 2,
                  boxShadow: 6,
                  px: 1.5,
                  py: 1,
                  minWidth: 280,
                  maxWidth: 520,
                  fontSize: 14,
                },
              },
              success: {
                sx: { borderRadius: 2, boxShadow: 6, px: 1.5, py: 1, minWidth: 280, maxWidth: 520 },
              },
              info: {
                sx: { borderRadius: 2, boxShadow: 6, px: 1.5, py: 1, minWidth: 280, maxWidth: 520 },
              },
              warning: {
                sx: { borderRadius: 2, boxShadow: 6, px: 1.5, py: 1, minWidth: 280, maxWidth: 520 },
              },
              error: {
                sx: { borderRadius: 2, boxShadow: 6, px: 1.5, py: 1, minWidth: 280, maxWidth: 520 },
              },
            }}
          >
            <App />
          </SnackbarProvider>
      </ThemeProvider>
    </BrowserRouter>
  </React.StrictMode>
);

import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { SnackbarProvider } from "notistack";
import { CssBaseline, ThemeProvider } from "@mui/material";

import App from "./App";
import "reactflow/dist/style.css";
import "./styles/reactflow-overrides.css";

import { appTheme } from "./theme";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ThemeProvider theme={appTheme}>
      <CssBaseline />
        <BrowserRouter>
          <SnackbarProvider
            maxSnack={4}
            preventDuplicate
            dense
            anchorOrigin={{ vertical: "top", horizontal: "right" }}
            autoHideDuration={3000}
            ComponentsProps={{
              default: {
                sx: {
                  borderRadius: 2,
                  boxShadow: 6,
                  px: 1.5,
                  py: 1,
                  minWidth: 280,
                  maxWidth: 520,
                  fontSize: 14,
                },
              },
              success: {
                sx: { borderRadius: 2, boxShadow: 6, px: 1.5, py: 1, minWidth: 280, maxWidth: 520 },
              },
              info: {
                sx: { borderRadius: 2, boxShadow: 6, px: 1.5, py: 1, minWidth: 280, maxWidth: 520 },
              },
              warning: {
                sx: { borderRadius: 2, boxShadow: 6, px: 1.5, py: 1, minWidth: 280, maxWidth: 520 },
              },
              error: {
                sx: { borderRadius: 2, boxShadow: 6, px: 1.5, py: 1, minWidth: 280, maxWidth: 520 },
              },
            }}
          >
            <App />
          </SnackbarProvider>
        </BrowserRouter>
    </ThemeProvider>
  </React.StrictMode>
);
