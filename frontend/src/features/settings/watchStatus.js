/**
 * One line that says what the folder watcher is doing, from the `watch`
 * object the server puts in the scan progress.
 *
 * Without it a watcher that quietly fell back to polling, or stopped with an
 * error, looks exactly like one that is working. Tones: "ok" (watching on
 * file events), "warn" (polling, or an error), "muted" (in between).
 */
export function describeWatch(watch, { wanted = null, now = Date.now() } = {}) {
  if (!watch) return null;

  // The checkbox is ahead of the server until Save is pressed.
  if (wanted === true && !watch.enabled) {
    return { tone: "muted", text: "Save settings to start watching." };
  }
  if (wanted === false && watch.enabled) {
    return { tone: "muted", text: "Save settings to stop watching." };
  }
  if (!watch.enabled) return null;

  switch (watch.state) {
    case "error":
      return {
        tone: "warn",
        text: `The watcher stopped: ${watch.error || "see the server log"}. It will try again; the daily scan still runs.`,
      };
    case "watching": {
      const lead =
        watch.mode === "polling"
          ? `Checking the folder every ${describeInterval(watch.poll_seconds)} — this storage does not report changes`
          : "Watching the folder";
      return { tone: watch.mode === "polling" ? "warn" : "ok", text: `${lead}${tail(watch, now)}` };
    }
    default:
      return { tone: "muted", text: "Starting the watcher…" };
  }
}

function tail(watch, now) {
  if (watch.last_import_at) {
    const added = watch.last_added || 0;
    const when = ago(watch.last_import_at, now);
    return added > 0
      ? ` · picked up ${added} track${added === 1 ? "" : "s"} ${when}`
      : ` · last import ${when}, nothing new`;
  }
  if (watch.pending > 0) {
    return ` · ${watch.pending} file${watch.pending === 1 ? "" : "s"} landing`;
  }
  return "";
}

export function describeInterval(seconds) {
  const total = Number(seconds) || 0;
  if (total < 60) return `${total} seconds`;
  const minutes = Math.round(total / 60);
  return `${minutes} minute${minutes === 1 ? "" : "s"}`;
}

/** Server timestamps are epoch seconds. */
export function ago(epochSeconds, now = Date.now()) {
  const elapsed = Math.max(0, now / 1000 - epochSeconds);
  if (elapsed < 60) return "just now";
  if (elapsed < 3600) return `${Math.floor(elapsed / 60)} min ago`;
  if (elapsed < 86400) {
    const hours = Math.floor(elapsed / 3600);
    return `${hours} hour${hours === 1 ? "" : "s"} ago`;
  }
  const days = Math.floor(elapsed / 86400);
  return `${days} day${days === 1 ? "" : "s"} ago`;
}
