import React, { createContext, useContext, useMemo, useState } from "react";

type LogDict = {
  ts: string;
  level: string;
  message: string;
  kind: string;
  payload?: any;
};

type OutputState = {
  currentJobId?: string;
  lines: string[];
  setCurrentJobId: (id?: string) => void;
  setLines: (lines: string[] | LogDict[]) => void;
  clear: () => void;
};

const Ctx = createContext<OutputState | null>(null);

// ------------------------------------------------------------
// FORMATTER: converts backend dictionaries → readable strings
// ------------------------------------------------------------
function formatLogEntry(entry: LogDict): string {
  const ts = new Date(entry.ts).toISOString();
  const lvl = entry.level.toUpperCase().padEnd(5);
  const kind = entry.kind;
  const msg = entry.message;
  return `[${ts}] [${lvl}] [${kind}] ${msg}`;
}

export function OutputProvider({ children }: { children: React.ReactNode }) {
  const [currentJobId, setCurrentJobId] = useState<string | undefined>(undefined);
  const [lines, _setLines] = useState<string[]>([]);

  const setLines = (incoming: string[] | LogDict[]) => {
    if (incoming.length === 0) {
      _setLines([]);
      return;
    }

    // If first element is a dictionary → format them
    if (typeof incoming[0] === "object") {
      const formatted = (incoming as LogDict[]).map(formatLogEntry);
      _setLines(formatted);
    } else {
      // Already strings
      _setLines(incoming as string[]);
    }
  };

  const value = useMemo(
    () => ({
      currentJobId,
      lines,
      setCurrentJobId,
      setLines,
      clear: () => {
        setCurrentJobId(undefined);
        _setLines([]);
      }
    }),
    [currentJobId, lines]
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useOutput() {
  const v = useContext(Ctx);
  if (!v) throw new Error("useOutput must be used within OutputProvider");
  return v;
}