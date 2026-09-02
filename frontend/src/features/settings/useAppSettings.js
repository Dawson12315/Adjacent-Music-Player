import { useCallback, useEffect, useState } from "react";

import { useNotifications } from "../../contexts/NotificationContext";
import * as settingsService from "../../services/settingsService";

const EMPTY_SETTINGS = settingsService.toAppSettings({});

/**
 * Loads and saves the app settings row.
 *
 * Settings are admin-only and are now fetched when this screen opens rather than during
 * application startup, where a 403 for a non-admin user would have failed the entire
 * library load.
 *
 * The saved response is mapped back through the same shape helper as the read. The
 * previous version rebuilt state from only four of the ten fields, so a second save sent
 * the missing ones as false and silently cancelled scheduled Last.fm enrichment.
 */
export function useAppSettings({ enabled = true } = {}) {
  const { notify } = useNotifications();

  const [settings, setSettings] = useState(EMPTY_SETTINGS);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    // Non-admins never fetch: the endpoint is admin-only and the 403 toast
    // ("Admin access required") is noise on a page they legitimately opened.
    if (!enabled) {
      setIsLoading(false);
      return undefined;
    }

    const controller = new AbortController();

    async function load() {
      try {
        const data = await settingsService.getSettings({ signal: controller.signal });

        if (!controller.signal.aborted) {
          setSettings(data);
        }
      } catch (error) {
        if (error.name !== "AbortError") {
          notify(error.message || "Could not load settings.");
        }
      } finally {
        if (!controller.signal.aborted) {
          setIsLoading(false);
        }
      }
    }

    load();

    return () => controller.abort();
  }, [notify, enabled]);

  const updateField = useCallback((key, value) => {
    setSettings((previous) => ({ ...previous, [key]: value }));
  }, []);

  const toggleField = useCallback((key) => {
    setSettings((previous) => ({ ...previous, [key]: !previous[key] }));
  }, []);

  const save = useCallback(async () => {
    setIsSaving(true);

    try {
      const saved = await settingsService.saveSettings(settings);
      setSettings(saved);
      notify("Settings saved successfully.");
    } catch (error) {
      notify(error.message || "Failed to save settings.");
    } finally {
      setIsSaving(false);
    }
  }, [settings, notify]);

  return { settings, setSettings, updateField, toggleField, save, isLoading, isSaving };
}
