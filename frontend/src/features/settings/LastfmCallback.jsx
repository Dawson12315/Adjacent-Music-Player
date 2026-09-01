import { useEffect, useRef } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

import { useNotifications } from "../../contexts/NotificationContext";
import { createLastfmSession } from "../../services/settingsService";

/**
 * Where Last.fm returns after the user authorises the app.
 *
 * This used to be an effect on the root component that sniffed
 * `window.location.pathname` and then rewrote history by hand. It is a route now, which
 * is the main practical reason routing was worth adding.
 */
export function LastfmCallback() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { notify } = useNotifications();

  const token = searchParams.get("token");
  const exchangedRef = useRef(false);

  useEffect(() => {
    // StrictMode runs effects twice in development; the token is single-use.
    if (exchangedRef.current) {
      return;
    }

    exchangedRef.current = true;

    async function exchange() {
      if (!token) {
        navigate("/settings", { replace: true });
        return;
      }

      try {
        await createLastfmSession(token);
        notify("Last.fm connected successfully.");
      } catch (error) {
        notify(error.message || "Failed to complete Last.fm connection.");
      } finally {
        navigate("/settings", { replace: true });
      }
    }

    exchange();
  }, [token, navigate, notify]);

  return <div className="state-message">Connecting to Last.fm...</div>;
}
