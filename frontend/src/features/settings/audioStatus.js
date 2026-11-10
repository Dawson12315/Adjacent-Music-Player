/** One line under the Analyse audio card: coverage, then what the worker is doing. */
export function describeAudioStatus(status, wanted) {
  if (!status) return null;
  const analysis = status.analysis || {};
  const available = analysis.available || {};
  const tracks = status.tracks || 0;
  const coverage = `${(status.profiled || 0).toLocaleString()} of ${tracks.toLocaleString()} tracks profiled, ${(status.flagged || 0).toLocaleString()} flagged`;

  if (!available.sound && !available.flags) {
    return { tone: "warn", text: `${coverage}. This server cannot analyse audio (the analysis libraries are not installed).` };
  }
  if (analysis.is_running) {
    return { tone: "ok", text: `${coverage}. Listening to a track now, ${analysis.queued || 0} waiting.` };
  }
  if (wanted && !analysis.enabled) return { tone: "muted", text: `${coverage}. Save settings to turn analysis on.` };
  if (!wanted && analysis.enabled) return { tone: "muted", text: `${coverage}. Save settings to turn analysis off.` };
  if (!analysis.enabled) return { tone: "muted", text: `${coverage}. Analysis is off.` };
  if (analysis.last_error) return { tone: "warn", text: `${coverage}. Last attempt: ${analysis.last_error}` };
  const flagsNote = available.flags ? "" : " Language and vocal flags need the lyrics model runtime.";
  return {
    tone: "ok",
    text: `${coverage}. Ready${analysis.done ? `; ${analysis.done} measured this session` : ""}.${flagsNote}`,
  };
}

/** "12,340 vocal · 1,200 instrumental · 8 languages · 340 explicit", or null before anything is known. */
export function describeCoverage(status) {
  if (!status) return null;
  const parts = [];
  if (status.vocal) parts.push(`${status.vocal.toLocaleString()} vocal`);
  if (status.instrumental) parts.push(`${status.instrumental.toLocaleString()} instrumental`);
  const languages = Object.keys(status.languages || {}).length;
  if (languages) parts.push(`${languages} ${languages === 1 ? "language" : "languages"}`);
  if (status.explicit) parts.push(`${status.explicit.toLocaleString()} explicit`);
  return parts.length ? parts.join(" · ") : null;
}
