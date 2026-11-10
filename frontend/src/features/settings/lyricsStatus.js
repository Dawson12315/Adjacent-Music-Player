/** One line under the Generate lyrics card: coverage, then what the worker is doing. */
export function describeStatus(status, wanted) {
  if (!status) return null;
  const generation = status.generation || {};
  const coverage = `${(status.with_lyrics || 0).toLocaleString()} of ${(status.tracks || 0).toLocaleString()} tracks have lyrics, ${(status.timed || 0).toLocaleString()} timed`;

  if (!generation.available) {
    return { tone: "warn", text: `${coverage}. This server cannot generate lyrics (the model runtime is not installed).` };
  }
  if (generation.is_running) {
    return { tone: "ok", text: `${coverage}. Working on a track now, ${generation.queued || 0} waiting.` };
  }
  if (wanted && !generation.enabled) return { tone: "muted", text: `${coverage}. Save settings to turn generation on.` };
  if (!wanted && generation.enabled) return { tone: "muted", text: `${coverage}. Save settings to turn generation off.` };
  if (!generation.enabled) return { tone: "muted", text: `${coverage}. Generation is off.` };
  if (generation.last_error) return { tone: "warn", text: `${coverage}. Last attempt: ${generation.last_error}` };
  return {
    tone: "ok",
    text: `${coverage}. Ready${generation.done ? `; ${generation.done} generated this session` : ""}.`,
  };
}
