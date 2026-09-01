import { useCallback, useEffect, useRef, useState } from "react";

/**
 * A message that clears itself after a delay. Used for form-scoped feedback that should
 * not linger. The timeout is cleared on unmount and whenever the message changes, so a
 * rapid sequence of messages cannot leave a stale timer behind.
 */
export function useTransientMessage(durationMs = 5000) {
  const [message, setMessage] = useState("");
  const timeoutRef = useRef(null);

  const clear = useCallback(() => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
      timeoutRef.current = null;
    }

    setMessage("");
  }, []);

  useEffect(() => {
    if (!message) {
      return undefined;
    }

    timeoutRef.current = setTimeout(() => {
      timeoutRef.current = null;
      setMessage("");
    }, durationMs);

    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
        timeoutRef.current = null;
      }
    };
  }, [message, durationMs]);

  return [message, setMessage, clear];
}
