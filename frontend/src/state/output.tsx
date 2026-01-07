import React, { createContext, useContext, useMemo, useState } from "react";

type OutputState = {
  currentJobId?: string;
  lines: string[];
  setCurrentJobId: (id?: string) => void;
  setLines: (lines: string[]) => void;
  clear: () => void;
};

const Ctx = createContext<OutputState | null>(null);

export function OutputProvider({ children }: { children: React.ReactNode }) {
  const [currentJobId, setCurrentJobId] = useState<string | undefined>(undefined);
  const [lines, setLines] = useState<string[]>([]);

  const value = useMemo(
    () => ({
      currentJobId,
      lines,
      setCurrentJobId,
      setLines,
      clear: () => {
        setCurrentJobId(undefined);
        setLines([]);
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
