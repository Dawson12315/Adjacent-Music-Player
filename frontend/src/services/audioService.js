import { apiClient } from "./apiClient";

/**
 * Audio analysis: what the server has heard in the library (sound profiles,
 * vocal / language / explicit flags) and an admin's say over a track's flags.
 * Everything runs on the server; see docs/audio-analysis.md.
 */

export function getAudioStatus(options) {
  return apiClient.get("/api/audio/status", options);
}

/** Start on the backlog now rather than tonight. */
export function analyseNow() {
  return apiClient.post("/api/audio/analyse", {});
}

/** Only the fields given are changed; the server keeps an admin's word. */
export function setTrackFlags(trackId, flags) {
  return apiClient.put(`/api/tracks/${trackId}/flags`, flags);
}

/** Back to detected, and listen again. */
export function resetTrackFlags(trackId) {
  return apiClient.delete(`/api/tracks/${trackId}/flags`);
}

const FLAG_WORDS = {
  vocal: "vocal",
  instrumental: "instrumental",
  explicit: "explicit",
  clean: "clean",
};

/** One short line for a track's flags: "Instrumental · detected" or "Explicit · set by an admin". */
export function describeFlags(flags) {
  if (!flags) return null;
  const parts = [];
  if (flags.vocal_state) parts.push(FLAG_WORDS[flags.vocal_state] || flags.vocal_state);
  if (flags.language) parts.push(flags.language.toUpperCase());
  if (flags.explicit_state) parts.push(FLAG_WORDS[flags.explicit_state] || flags.explicit_state);
  if (!parts.length) return null;
  const text = parts.join(" · ");
  const capitalised = text.charAt(0).toUpperCase() + text.slice(1);
  return `${capitalised} · ${flags.set_by === "admin" ? "set by an admin" : "detected"}`;
}
