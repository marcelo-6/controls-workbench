import React, { useMemo, useState } from "react";
import { Routes, Route, Navigate, Link as RouterLink, useLocation } from "react-router-dom";
import {
  AppBar,
  Box,
  Breadcrumbs,
  Divider,
  Drawer,
  IconButton,
  Link,
  List,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Toolbar,
  Typography,
  Tooltip,
} from "@mui/material";

import MenuIcon from "@mui/icons-material/Menu";
import LogoutIcon from "@mui/icons-material/Logout";
import HubIcon from "@mui/icons-material/Hub";
import HelpOutlineIcon from "@mui/icons-material/HelpOutline";
import Brightness4Icon from "@mui/icons-material/Brightness4";
import Brightness7Icon from "@mui/icons-material/Brightness7";

import IgnitionGraphPage from "../pages/IgnitionGraphPage";
import BottomPanels from "./BottomPanels";
import { OutputProvider } from "../state/output";
import { useThemeMode } from "../theme-mode";
import { VersionChip } from "./VersionChip";

const drawerWidth = 260;

type Props = {
  onLogout: () => void;
};

export default function Shell({ onLogout }: Props) {
  const [collapsed, setCollapsed] = useState(true);
  const location = useLocation();
  const { mode, toggleMode } = useThemeMode();

  // -----------------------------
  // NAV ITEMS
  // -----------------------------
  const navItems = useMemo(
    () => [
      {
        label: "Ignition Graph",
        to: "/tools/ignition/graph",
        icon: <HubIcon sx={{ fontSize: 22 }} />,
      },
    ],
    []
  );

  // -----------------------------
  // BREADCRUMB BUILDER
  // -----------------------------
  const breadcrumbParts = location.pathname
    .split("/")
    .filter(Boolean)
    .map((p) => p.replace(/-/g, " "));

  const breadcrumbDisplay = breadcrumbParts.map((p) =>
    p.charAt(0).toUpperCase() + p.slice(1)
  );

  return (
    <OutputProvider>
      <Box sx={{ display: "flex", height: "100vh" }}>

        {/* ---------------------------------- */}
        {/* TOP BAR */}
        {/* ---------------------------------- */}
        <AppBar
          position="fixed"
          color="primary"
          enableColorOnDark
          sx={{
            zIndex: (t) => t.zIndex.drawer + 1,
            backdropFilter: "blur(8px)",
          }}
        >
          <Toolbar sx={{ gap: 2 }}>

            {/* Sidebar toggle */}
            <IconButton
              color="inherit"
              edge="start"
              onClick={() => setCollapsed((v) => !v)}
            >
              <MenuIcon />
            </IconButton>

            {/* Breadcrumbs */}
            <Breadcrumbs
              aria-label="breadcrumb"
              sx={{
                flex: 1,
                color: "inherit",
                "& .MuiBreadcrumbs-separator": { color: "inherit" },
              }}
            >
              <Link
                component={RouterLink}
                underline="hover"
                color="inherit"
                to="/"
                sx={{ fontWeight: 500 }}
              >
                Home
              </Link>

              {breadcrumbDisplay.map((crumb, idx) => {
                const path = "/" + breadcrumbParts.slice(0, idx + 1).join("/");
                const isLast = idx === breadcrumbDisplay.length - 1;

                return isLast ? (
                  <Typography key={idx} color="inherit" sx={{ fontWeight: 600 }}>
                    {crumb}
                  </Typography>
                ) : (
                  <Link
                    key={idx}
                    component={RouterLink}
                    underline="hover"
                    color="inherit"
                    to={path}
                    sx={{ fontWeight: 500 }}
                  >
                    {crumb}
                  </Link>
                );
              })}
            </Breadcrumbs>

            <VersionChip version={__UI_VERSION__} />

            {/* Theme toggle */}
            <Tooltip title={mode === "dark" ? "Switch to light mode" : "Switch to dark mode"}>
              <IconButton color="inherit" onClick={toggleMode} size="small">
                {mode === "dark" ? <Brightness7Icon /> : <Brightness4Icon />}
              </IconButton>
            </Tooltip>

            {/* API Docs */}
            <Tooltip title="Open API Docs">
              <IconButton
                color="inherit"
                onClick={() => window.open("http://localhost:8000/docs", "_blank")}
              >
                <HelpOutlineIcon />
              </IconButton>
            </Tooltip>

            {/* Logout */}
            <Tooltip title="Logout">
              <IconButton color="inherit" onClick={onLogout}>
                <LogoutIcon />
              </IconButton>
            </Tooltip>
          </Toolbar>
        </AppBar>

        {/* ---------------------------------- */}
        {/* SIDEBAR */}
        {/* ---------------------------------- */}
        <Drawer
          variant="permanent"
          sx={{
            width: collapsed ? 72 : drawerWidth,
            flexShrink: 0,
            transition: "width 0.25s ease",
            [`& .MuiDrawer-paper`]: {
              width: collapsed ? 72 : drawerWidth,
              boxSizing: "border-box",
              overflowX: "hidden",
              transition: "width 0.25s ease",
              borderRight: "1px solid",
              borderColor: "divider",
            },
          }}
        >
          <Toolbar />

          <Box sx={{ overflowY: "auto", mt: 1 }}>
            <List>
              {navItems.map((it) => {
                const active = location.pathname.startsWith(it.to);

                return (
                  <ListItemButton
                    key={it.to}
                    component={RouterLink}
                    to={it.to}
                    selected={active}
                    sx={{
                      justifyContent: collapsed ? "center" : "flex-start",
                      px: collapsed ? 1 : 2,
                      mx: collapsed ? 0.5 : 1,
                      my: 0.5,
                      borderRadius: 1,
                      transition: "all 0.2s ease",
                      color: active ? "primary.contrastText" : "text.primary",
                      bgcolor: active ? "primary.main" : "transparent",
                      "&:hover": {
                        bgcolor: active ? "primary.dark" : "action.hover",
                      },
                    }}
                  >
                    <Tooltip
                      title={collapsed ? it.label : ""}
                      placement="right"
                      disableHoverListener={!collapsed}
                    >
                      <ListItemIcon
                        sx={{
                          minWidth: 0,
                          mr: collapsed ? 0 : 1.5,
                          justifyContent: "center",
                          color: "inherit", // theme-adaptive icon
                        }}
                      >
                        {it.icon}
                      </ListItemIcon>
                    </Tooltip>

                    {!collapsed && (
                      <ListItemText
                        primary={it.label}
                        primaryTypographyProps={{
                          fontSize: 15,
                          fontWeight: active ? 600 : 400,
                        }}
                      />
                    )}
                  </ListItemButton>
                );
              })}
            </List>

            <Divider sx={{ my: 1 }} />
          </Box>
        </Drawer>

        {/* ---------------------------------- */}
        {/* MAIN CONTENT */}
        {/* ---------------------------------- */}
        <Box component="main" sx={{ flex: 1, display: "flex", flexDirection: "column" }}>
          <Toolbar />

          <Box sx={{ flex: 1, minHeight: 0, position: "relative" }}>
            <Routes>
              <Route path="/tools/ignition/graph" element={<IgnitionGraphPage />} />
              <Route path="*" element={<Navigate to="/tools/ignition/graph" replace />} />
            </Routes>
          </Box>

          <BottomPanels />
        </Box>
      </Box>
    </OutputProvider>
  );
}