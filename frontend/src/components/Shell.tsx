import React, { useMemo, useState } from "react";
import { Routes, Route, Navigate, Link as RouterLink, useLocation } from "react-router-dom";
import {
  AppBar,
  Box,
  Divider,
  Drawer,
  IconButton,
  List,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Toolbar,
  Typography,
  Tooltip
} from "@mui/material";
import MenuIcon from "@mui/icons-material/Menu";
import LogoutIcon from "@mui/icons-material/Logout";
import HubIcon from "@mui/icons-material/Hub";
import HelpOutlineIcon from "@mui/icons-material/HelpOutline";

import IgnitionGraphPage from "../pages/IgnitionGraphPage";
import BottomPanels from "./BottomPanels";
import { OutputProvider } from "../state/output";

import Brightness4Icon from "@mui/icons-material/Brightness4";
import Brightness7Icon from "@mui/icons-material/Brightness7";
import { useThemeMode } from "../theme-mode";

const drawerWidth = 260;

type Props = {
  onLogout: () => void;
};

export default function Shell({ onLogout }: Props) {
  const [collapsed, setCollapsed] = useState(false);
  const location = useLocation();
  const { mode, toggleMode } = useThemeMode();

  const navItems = useMemo(
    () => [
      {
        label: "Ignition Graph",
        to: "/tools/ignition/graph",
        icon: <HubIcon />
      }
    ],
    []
  );

  return (
    <OutputProvider>
      <Box sx={{ display: "flex", height: "100vh" }}>
        <AppBar position="fixed" sx={{ zIndex: (t) => t.zIndex.drawer + 1 }}>
          <Toolbar sx={{ gap: 1 }}>
            <IconButton color="inherit" edge="start" onClick={() => setCollapsed((v) => !v)}>
              <MenuIcon />
            </IconButton>
            <Typography variant="h6" sx={{ flex: 1 }}>
              Controls Workbench
            </Typography>
            <Tooltip title={mode === "dark" ? "Switch to light mode" : "Switch to dark mode"}>
              <IconButton onClick={toggleMode} size="small" sx={{ ml: 1 }}>
                {mode === "dark" ? <Brightness7Icon fontSize="small" /> : <Brightness4Icon fontSize="small" />}
              </IconButton>
            </Tooltip>
            <Tooltip title="Open API Docs">
              <IconButton
                color="inherit"
                onClick={() => window.open("http://localhost:8000/docs", "_blank")}
              >
                <HelpOutlineIcon />
              </IconButton>
            </Tooltip>
            <Tooltip title="Logout">
              <IconButton color="inherit" onClick={onLogout}>
                <LogoutIcon />
              </IconButton>
            </Tooltip>
          </Toolbar>
        </AppBar>

        <Drawer
          variant="permanent"
          sx={{
            width: collapsed ? 72 : drawerWidth,
            flexShrink: 0,
            [`& .MuiDrawer-paper`]: {
              width: collapsed ? 72 : drawerWidth,
              boxSizing: "border-box",
              overflowX: "hidden"
            }
          }}
        >
          <Toolbar />
          <Box sx={{ overflowY: "auto", overflowX: "hidden" }}>
            <List>
              {navItems.map((it) => (
                <ListItemButton
                  key={it.to}
                  component={RouterLink}
                  to={it.to}
                  selected={location.pathname.startsWith(it.to)}
                  sx={{
                    justifyContent: collapsed ? "center" : "flex-start",
                    px: collapsed ? 1 : 2
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
                        color: "text.secondary"
                      }}
                    >
                      {it.icon}
                    </ListItemIcon>
                  </Tooltip>

                  {!collapsed && <ListItemText primary={it.label} />}
                </ListItemButton>
              ))}
            </List>
            <Divider />
          </Box>
        </Drawer>


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
