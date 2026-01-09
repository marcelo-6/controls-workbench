import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { SnackbarProvider } from "notistack";
import { CssBaseline, ThemeProvider } from "@mui/material";

import App from "./App";
import "reactflow/dist/style.css";
import "./styles/reactflow-overrides.css";

import { ThemeModeProvider, useThemeMode } from "./theme-mode";
import { getAppTheme } from "./theme";

function ThemedApp() {
  const { mode } = useThemeMode();
  const theme = React.useMemo(() => getAppTheme(mode), [mode]);

  return (
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
            <BrowserRouter>
            <App />
            </BrowserRouter>
          </SnackbarProvider>
    </ThemeProvider>
  );
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ThemeModeProvider>
      <ThemedApp />
    </ThemeModeProvider>
  </React.StrictMode>
);
