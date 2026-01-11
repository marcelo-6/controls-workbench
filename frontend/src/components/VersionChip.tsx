import React from "react";
import { Chip, Tooltip } from "@mui/material";
import InfoOutlinedIcon from "@mui/icons-material/InfoOutlined";

type Props = {
  version: string; // e.g. __UI_VERSION__
};

export function VersionChip({ version }: Props) {
  return (
    <Tooltip title={`UI v${version}`} arrow>
      <Chip
        size="small"
        icon={<InfoOutlinedIcon fontSize="small" />}
        label={`v${version}`}
        variant="outlined"
        sx={{
          borderRadius: 999,
          fontWeight: 600,
          letterSpacing: 0.2,
          "& .MuiChip-icon": { ml: 0.75 },
        }}
      />
    </Tooltip>
  );
}
