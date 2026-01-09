import { alpha, createTheme } from "@mui/material/styles";

/**
 * App theme.
 *
 * Goal: a "shadcn-like" dark dashboard look:
 * - near-black background with subtle gradient
 * - cards/panels with thin borders + soft shadow
 * - compact, rounded controls
 */
export const appTheme = createTheme({
  palette: {
    mode: "dark",

    background: {
      default: "#0B0B0C",
      paper: "#111113"
    },
    text: {
      primary: "#FAFAFA",
      secondary: alpha("#FAFAFA", 0.64)
    },
    divider: alpha("#FAFAFA", 0.10)
  },

  typography: {
    fontFamily:
      "ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, Apple Color Emoji, Segoe UI Emoji",
    h6: { fontWeight: 650 },
    subtitle2: { fontWeight: 650 }
  },

  shape: { borderRadius: 12 },

  components: {
    MuiCssBaseline: {
      styleOverrides: {
        body: {
          backgroundImage:
            "radial-gradient(1200px 600px at 20% 0%, rgba(255,255,255,0.06), transparent 60%), radial-gradient(900px 500px at 80% 10%, rgba(255,255,255,0.04), transparent 60%)",
          backgroundColor: "#0B0B0C"
        }
      }
    },

    MuiPaper: {
      styleOverrides: {
        root: {
          border: `1px solid ${alpha("#FAFAFA", 0.10)}`,
          backgroundImage:
            "linear-gradient(180deg, rgba(255,255,255,0.03), rgba(255,255,255,0.00))",
          boxShadow:
            "0 1px 0 rgba(255,255,255,0.04), 0 10px 30px rgba(0,0,0,0.45)"
        }
      }
    },

    MuiCard: {
      defaultProps: { variant: "outlined" },
      styleOverrides: { root: { borderColor: alpha("#FAFAFA", 0.10) } }
    },

    MuiAppBar: {
      styleOverrides: {
        root: {
          border: "none",
          boxShadow: "none",
          backgroundColor: alpha("#0B0B0C", 0.72),
          backdropFilter: "blur(10px)",
          borderBottom: `1px solid ${alpha("#FAFAFA", 0.10)}`
        }
      }
    },

    MuiDrawer: {
      styleOverrides: {
        paper: {
          border: "none",
          boxShadow: "none",
          backgroundColor: alpha("#0B0B0C", 0.85),
          backdropFilter: "blur(8px)",
          borderRight: `1px solid ${alpha("#FAFAFA", 0.10)}`
        }
      }
    },

    MuiDivider: {
      styleOverrides: { root: { borderColor: alpha("#FAFAFA", 0.10) } }
    },

    MuiButton: {
      defaultProps: { disableElevation: true },
      styleOverrides: {
        root: { borderRadius: 12, textTransform: "none", fontWeight: 650 },
        outlined: { borderColor: alpha("#FAFAFA", 0.12) }
      }
    },

    MuiTextField: {
      defaultProps: { size: "small" }
    },

    MuiOutlinedInput: {
      styleOverrides: {
        root: {
          backgroundColor: alpha("#FAFAFA", 0.03),
          borderRadius: 12,
          "& .MuiOutlinedInput-notchedOutline": { borderColor: alpha("#FAFAFA", 0.12) },
          "&:hover .MuiOutlinedInput-notchedOutline": { borderColor: alpha("#FAFAFA", 0.18) },
          "&.Mui-focused .MuiOutlinedInput-notchedOutline": { borderColor: alpha("#FAFAFA", 0.28) }
        }
      }
    },

    MuiChip: {
      styleOverrides: { root: { borderColor: alpha("#FAFAFA", 0.12) } }
    },

    MuiListItemButton: {
      styleOverrides: {
        root: {
          borderRadius: 12,
          marginLeft: 8,
          marginRight: 8,
          "&.Mui-selected": { backgroundColor: alpha("#FAFAFA", 0.06) },
          "&.Mui-selected:hover": { backgroundColor: alpha("#FAFAFA", 0.08) }
        }
      }
    }
  }
});
