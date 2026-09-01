import { useMemo } from "react";

import { NotificationContext } from "./NotificationContext";
import { useTransientMessage } from "../hooks/useTransientMessage";

/**
 * App-level notices. Deliberately minimal: one message at a time, self-clearing, which
 * is what the settings screen already did — just reachable from anywhere now, so handlers
 * that previously failed silently into console.error have somewhere to report to.
 */
export function NotificationProvider({ children }) {
  const [notice, setNotice, clearNotice] = useTransientMessage(5000);

  const value = useMemo(
    () => ({ notice, notify: setNotice, clearNotice }),
    [notice, setNotice, clearNotice],
  );

  return (
    <NotificationContext.Provider value={value}>{children}</NotificationContext.Provider>
  );
}
