import { createContext, useContext } from "react";

export const ScanContext = createContext(null);

export function useScan() {
  const context = useContext(ScanContext);

  if (!context) {
    throw new Error("useScan must be used within ScanProvider");
  }

  return context;
}
