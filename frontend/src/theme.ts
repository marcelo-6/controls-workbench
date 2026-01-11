import { alpha, createTheme } from "@mui/material/styles";
import type { PaletteMode } from "@mui/material";

/**
 * Build the app theme for a given mode.
 */
export function getAppTheme(mode: PaletteMode) {
  const isDark = mode === "dark";

  const bgDefault = isDark ? "#0B0B0C" : "#F6F7FB";
  const paper = isDark ? "#111113" : "#FFFFFF";
  const textPrimary = isDark ? "#FAFAFA" : "#0B0B0C";

  return createTheme({
    palette: {
      mode,
      background: {
        default: bgDefault,
        paper
      },
      text: {
        primary: textPrimary,
        secondary: alpha(textPrimary, 0.64)
      },
      divider: alpha(textPrimary, isDark ? 0.10 : 0.12),
      primary: {
        main: textPrimary,
        contrastText: textPrimary,
      },
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
          body: isDark
            ? {
                backgroundImage:
                  "radial-gradient(1200px 600px at 20% 0%, rgba(255,255,255,0.06), transparent 60%), radial-gradient(900px 500px at 80% 10%, rgba(255,255,255,0.04), transparent 60%)",
                backgroundColor: bgDefault
              }
            : {
                backgroundImage:
                  "radial-gradient(1200px 600px at 20% 0%, rgba(0,0,0,0.05), transparent 60%), radial-gradient(900px 500px at 80% 10%, rgba(0,0,0,0.03), transparent 60%)",
                backgroundColor: bgDefault
              }
        }
      },

      MuiPaper: {
        styleOverrides: {
          root: {
            border: `1px solid ${alpha(textPrimary, isDark ? 0.10 : 0.10)}`,
            backgroundImage: isDark
              ? "linear-gradient(180deg, rgba(255,255,255,0.03), rgba(255,255,255,0.00))"
              : "linear-gradient(180deg, rgba(0,0,0,0.02), rgba(0,0,0,0.00))",
            boxShadow: isDark
              ? "0 1px 0 rgba(255,255,255,0.04), 0 10px 30px rgba(0,0,0,0.45)"
              : "0 1px 0 rgba(0,0,0,0.03), 0 10px 30px rgba(0,0,0,0.10)"
          }
        }
      },

      MuiAppBar: {
        styleOverrides: {
          root: {
            border: "none",
            boxShadow: "none",
            backgroundColor: isDark ? alpha("#0B0B0C", 0.72) : alpha("#FFFFFF", 0.72),
            backdropFilter: "blur(10px)",
            borderBottom: `1px solid ${alpha(textPrimary, isDark ? 0.10 : 0.10)}`
          }
        }
      },

      MuiDrawer: {
        styleOverrides: {
          paper: {
            border: "none",
            boxShadow: "none",
            backgroundColor: isDark ? alpha("#0B0B0C", 0.85) : alpha("#FFFFFF", 0.85),
            backdropFilter: "blur(8px)",
            borderRight: `1px solid ${alpha(textPrimary, isDark ? 0.10 : 0.10)}`
          }
        }
      },

      MuiButton: {
        defaultProps: { disableElevation: true },
        styleOverrides: {
          root: { borderRadius: 12, textTransform: "none", fontWeight: 650 }
        }
      },

      MuiOutlinedInput: {
        styleOverrides: {
          root: {
            backgroundColor: isDark ? alpha("#FAFAFA", 0.03) : alpha("#0B0B0C", 0.03),
            borderRadius: 12,
            "& .MuiOutlinedInput-notchedOutline": {
              borderColor: alpha(textPrimary, isDark ? 0.12 : 0.14)
            },
            "&:hover .MuiOutlinedInput-notchedOutline": {
              borderColor: alpha(textPrimary, isDark ? 0.18 : 0.20)
            },
            "&.Mui-focused .MuiOutlinedInput-notchedOutline": {
              borderColor: alpha(textPrimary, isDark ? 0.28 : 0.30)
            }
          }
        }
      }
    }
  });
}
