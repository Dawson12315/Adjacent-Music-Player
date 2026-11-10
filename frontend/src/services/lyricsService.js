import { apiClient } from "./apiClient";

/**
 * A track's lyrics, or null with the reason when it has none.
 *
 * The server answers 404 for "no lyrics", with a `generation` status that
 * says whether asking it to produce them is an option: "available", "queued",
 * "running", "failed" (with a reason), "off" (the admin switch) or
 * "unsupported" (no model on that server).
 */
export async function getLyrics(trackId, options) {
  try {
    const data = await apiClient.get(`/api/tracks/${trackId}/lyrics`, { ...options, noStore: true });
    return normalizeLyrics(data);
  } catch (error) {
    if (error?.status === 404 && error?.detail?.code === "no_lyrics") {
      return { none: true, generation: error.detail.generation || { state: "unsupported" } };
    }
    throw error;
  }
}

export function normalizeLyrics(data) {
  return {
    trackId: data.track_id,
    source: data.source,
    syncedSource: data.synced_source || null,
    plain: data.plain || "",
    synced: Array.isArray(data.synced) ? data.synced.map((line) => ({ t: Number(line.t) || 0, line: line.line })) : null,
    language: data.language || null,
    generated: Boolean(data.generated),
    model: data.model || null,
    confidence: data.confidence ?? null,
    updatedAt: data.updated_at || null,
  };
}

/**
 * Ask the server to produce lyrics for the track. Resolves to the generation
 * status. `force` (admin) throws away what the server produced before — a
 * transcription that stopped short — and does it again; the file's own words
 * are kept and re-timed.
 */
export function requestLyrics(trackId, { force = false } = {}) {
  return apiClient.post(`/api/tracks/${trackId}/lyrics/generate${force ? "?force=1" : ""}`, undefined, { noStore: true });
}

/** Save typed or corrected lyrics (admin). Either plain text or timed lines. */
export async function saveLyrics(trackId, { plain, synced }) {
  const data = await apiClient.put(`/api/tracks/${trackId}/lyrics`, {
    plain: plain ?? null,
    synced: synced ? synced.map((line) => ({ t: Math.max(0, Number(line.t) || 0), line: line.line })) : null,
  });
  return normalizeLyrics(data);
}

/** Drop what Adjacent holds and read the file again (admin). */
export async function resetLyrics(trackId) {
  try {
    const data = await apiClient.delete(`/api/tracks/${trackId}/lyrics`);
    return normalizeLyrics(data);
  } catch (error) {
    if (error?.status === 404 && error?.detail?.code === "no_lyrics") {
      return { none: true, generation: error.detail.generation || { state: "unsupported" } };
    }
    throw error;
  }
}

/** Coverage and the generation worker's state, for the Settings card (admin). */
export function getLyricsStatus(options) {
  return apiClient.get("/api/lyrics/status", { ...options, noStore: true });
}

/** What the players say under the lyrics. */
export function describeLyricsSource(lyrics) {
  if (!lyrics || lyrics.none) return "";
  if (lyrics.source === "transcribed") {
    return `Generated on your server${lyrics.model ? ` (${lyrics.model})` : ""} · may contain errors`;
  }
  const words =
    lyrics.source === "user" ? "Edited in Adjacent" : lyrics.source === "sidecar" ? "From a lyrics file beside the track" : "From the file";
  if (lyrics.syncedSource === "aligned") return `${words} · timed on your server`;
  return words;
}

/** The line being sung at `position`, or -1 before the first. */
export function currentLineIndex(synced, position) {
  if (!Array.isArray(synced) || synced.length === 0) return -1;
  let index = -1;
  for (let i = 0; i < synced.length; i += 1) {
    if (synced[i].t <= position + 0.05) index = i;
    else break;
  }
  return index;
}
