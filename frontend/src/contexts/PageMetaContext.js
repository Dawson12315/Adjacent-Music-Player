import { createContext, useContext } from "react";

export const PageMetaContext = createContext(null);

export function usePageMeta() {
  const context = useContext(PageMetaContext);

  if (!context) {
    throw new Error("usePageMeta must be used within a PageMetaProvider");
  }

  return context;
}
