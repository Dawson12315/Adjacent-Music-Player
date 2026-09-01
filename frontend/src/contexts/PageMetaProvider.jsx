import { useCallback, useMemo, useState } from "react";

import { PageMetaContext } from "./PageMetaContext";

/**
 * Lets a routed view tell the page header what it is showing — a result count, the loaded
 * tracks for a Play button — without prop-drilling through the layout.
 *
 * This exists because the header and the view are siblings: the header sits above the
 * <Outlet>, but only the view knows how many results came back.
 */
export function PageMetaProvider({ children }) {
  const [meta, setMetaState] = useState({});

  const setPageMeta = useCallback((next) => {
    setMetaState((previous) => {
      const changed = Object.keys(next).some((key) => !Object.is(next[key], previous[key]));
      return changed ? { ...previous, ...next } : previous;
    });
  }, []);

  const value = useMemo(() => ({ meta, setPageMeta }), [meta, setPageMeta]);

  return <PageMetaContext.Provider value={value}>{children}</PageMetaContext.Provider>;
}
