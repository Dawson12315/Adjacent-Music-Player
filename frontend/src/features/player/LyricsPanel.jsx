import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { Icon } from "../../components/Icon";
import { useAuth } from "../../contexts/AuthContext";
import { describeFlags, setTrackFlags } from "../../services/audioService";
import { useNotifications } from "../../contexts/NotificationContext";
import { usePlayer, usePlayerProgress } from "../../contexts/PlayerContext";
import {
  currentLineIndex,
  describeLyricsSource,
  getLyrics,
  requestLyrics,
  resetLyrics,
  saveLyrics,
} from "../../services/lyricsService";

/** How often to ask again while the server is producing lyrics for this track. */
const GENERATING_POLL_MS = 5000;

function formatStamp(seconds) {
  const total = Math.max(0, Number(seconds) || 0);
  const minutes = Math.floor(total / 60);
  const rest = total - minutes * 60;
  return `[${String(minutes).padStart(2, "0")}:${rest.toFixed(2).padStart(5, "0")}]`;
}

/**
 * The words of the playing track, beside the player.
 *
 * Timed lyrics follow the playhead and a click on a line seeks to it; plain
 * lyrics scroll by hand. A track with none says so, and when the server can
 * produce them offers to, then polls until they arrive. An admin can edit:
 * paste the text, or step through it with "Stamp" as the song plays to time
 * each line — a whole song is timed in one playthrough.
 */
export function LyricsPanel() {
  const { currentTrack } = usePlayer();
  const { currentTime, seek } = usePlayerProgress();
  const { currentUser } = useAuth();
  const { notify } = useNotifications();
  const isAdmin = currentUser?.role === "admin";

  // An admin's word on the explicit flag: the server keeps it over its own guess.
  async function markExplicit(explicitState) {
    const trackId = state.lyrics?.trackId ?? currentTrack?.id;
    if (trackId == null) return;
    try {
      const flags = await setTrackFlags(trackId, { explicit_state: explicitState });
      setState((current) => (current.lyrics ? { ...current, lyrics: { ...current.lyrics, flags } } : current));
    } catch (problem) {
      notify?.(problem?.message || "Could not change the flag.", "error");
    }
  }
  const trackId = currentTrack?.id ?? null;

  const [state, setState] = useState({ status: "loading", lyrics: null, generation: null });
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");
  const [stamps, setStamps] = useState([]);
  const [saving, setSaving] = useState(false);
  // True from a Regenerate press until the server's new words (or a refusal) arrive.
  const [regenerating, setRegenerating] = useState(false);
  // The lyrics on screen when Regenerate was pressed: the job is done once a
  // later load brings back something else, not while these are still shown.
  const regenerateBaselineRef = useRef(null);
  const listRef = useRef(null);
  const lineRefs = useRef([]);

  const load = useCallback(
    async (signal) => {
      if (trackId == null) return;
      try {
        const result = await getLyrics(trackId, { signal });
        if (signal?.aborted) return;
        if (result.none) setState({ status: "none", lyrics: null, generation: result.generation });
        else setState({ status: "ready", lyrics: result, generation: null });
      } catch (error) {
        if (error?.name === "AbortError") return;
        setState({ status: "error", lyrics: null, generation: null });
      }
    },
    [trackId],
  );

  useEffect(() => {
    const controller = new AbortController();
    setState({ status: "loading", lyrics: null, generation: null });
    setEditing(false);
    setRegenerating(false);
    lineRefs.current = [];
    load(controller.signal);
    return () => controller.abort();
  }, [load]);

  // Poll while the server is working on this track — asked for by the
  // generate button, or by a regenerate that is still being redone.
  const working =
    regenerating || (state.status === "none" && (state.generation?.state === "queued" || state.generation?.state === "running"));
  useEffect(() => {
    if (!working) return undefined;
    const timer = setTimeout(() => load(), GENERATING_POLL_MS);
    return () => clearTimeout(timer);
  }, [working, load, state]);

  // A regenerate is over when the server's new timing or words are here,
  // or when it said it could not.
  useEffect(() => {
    if (!regenerating) return;
    const fresh = state.lyrics && state.lyrics !== regenerateBaselineRef.current;
    if (state.status === "ready" && fresh && state.lyrics.generated && state.lyrics.synced) setRegenerating(false);
    if (state.status === "none" && ["failed", "off", "unsupported"].includes(state.generation?.state)) setRegenerating(false);
  }, [regenerating, state]);

  const synced = state.lyrics?.synced || null;
  const activeIndex = synced ? currentLineIndex(synced, currentTime) : -1;

  useEffect(() => {
    if (editing || activeIndex < 0) return;
    const node = lineRefs.current[activeIndex];
    node?.scrollIntoView?.({ block: "center", behavior: "smooth" });
  }, [activeIndex, editing]);

  const lines = useMemo(() => {
    if (!state.lyrics) return [];
    return synced ? synced.map((line) => line.line) : state.lyrics.plain.split("\n");
  }, [state.lyrics, synced]);

  async function generate() {
    try {
      const status = await requestLyrics(trackId);
      setState({ status: "none", lyrics: null, generation: status });
    } catch (error) {
      notify(error?.detail?.message || error.message || "Could not ask the server for lyrics.");
    }
  }

  async function regenerate() {
    try {
      const status = await requestLyrics(trackId, { force: true });
      regenerateBaselineRef.current = state.lyrics;
      setRegenerating(true);
      // Words the file carries stay on screen while they are re-timed; a
      // transcription is gone until the new one arrives.
      setState((current) =>
        current.status === "ready" && current.lyrics?.source !== "transcribed"
          ? current
          : { status: "none", lyrics: null, generation: status },
      );
    } catch (error) {
      notify(error?.detail?.message || error.message || "Could not ask the server to regenerate.");
    }
  }

  function startEditing() {
    setDraft(state.lyrics?.plain || "");
    setStamps([]);
    setEditing(true);
  }

  const draftLines = useMemo(() => draft.split("\n").filter((line) => line.trim()), [draft]);

  function stampNext() {
    setStamps((current) => (current.length < draftLines.length ? [...current, currentTime] : current));
  }

  function undoStamp() {
    setStamps((current) => current.slice(0, -1));
  }

  async function save() {
    setSaving(true);
    try {
      const timed = stamps.length === draftLines.length && draftLines.length > 0;
      const saved = await saveLyrics(trackId, {
        plain: draft,
        synced: timed ? draftLines.map((line, index) => ({ t: stamps[index], line })) : null,
      });
      setState({ status: "ready", lyrics: saved, generation: null });
      setEditing(false);
      notify(timed ? "Lyrics saved with timing." : "Lyrics saved.");
    } catch (error) {
      notify(error.message || "Could not save the lyrics.");
    } finally {
      setSaving(false);
    }
  }

  async function reset() {
    setSaving(true);
    try {
      const result = await resetLyrics(trackId);
      if (result.none) setState({ status: "none", lyrics: null, generation: result.generation });
      else setState({ status: "ready", lyrics: result, generation: null });
      setEditing(false);
      notify("Back to what the file says.");
    } catch (error) {
      notify(error.message || "Could not reset the lyrics.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <aside className="lyrics-panel" aria-label="Lyrics">
      <div className="lyrics-panel__header">
        <h2>Lyrics</h2>
        {currentTrack ? <p>{currentTrack.title}</p> : <p>Nothing playing</p>}
      </div>

      {!currentTrack ? (
        <div className="lyrics-panel__empty">Play something to see its words here.</div>
      ) : editing ? (
        <div className="lyrics-panel__editor">
          <textarea
            className="input lyrics-panel__textarea"
            value={draft}
            onChange={(event) => {
              setDraft(event.target.value);
              setStamps([]);
            }}
            placeholder={"One line per line. Pasted LRC with [mm:ss.xx] stamps is understood."}
            aria-label="Lyrics text"
            spellCheck={false}
          />
          <div className="lyrics-panel__timing">
            <div className="lyrics-panel__timing-head">
              <span className="field__label">Time the lines</span>
              <span className="lyrics-panel__timing-count">
                {stamps.length} / {draftLines.length}
              </span>
            </div>
            <p className="field__hint">
              Play the song and press Stamp as each line begins. Stamp every line and the lyrics are saved with timing;
              stamp none and they are saved as text.
            </p>
            <div className="lyrics-panel__timing-next">
              {stamps.length < draftLines.length ? (
                <>
                  <span className="lyrics-panel__stamp">{formatStamp(currentTime)}</span>
                  <span className="lyrics-panel__next-line">{draftLines[stamps.length]}</span>
                </>
              ) : draftLines.length ? (
                <span className="lyrics-panel__next-line">Every line is timed.</span>
              ) : null}
            </div>
            <div className="settings-card__actions">
              <button className="btn btn--primary" type="button" onClick={stampNext} disabled={stamps.length >= draftLines.length}>
                Stamp
              </button>
              <button className="btn" type="button" onClick={undoStamp} disabled={!stamps.length}>
                Undo
              </button>
            </div>
          </div>
          <div className="settings-card__actions lyrics-panel__editor-actions">
            <button className="btn btn--primary" type="button" onClick={save} disabled={saving || !draft.trim()}>
              {saving ? "Saving…" : "Save"}
            </button>
            <button className="btn" type="button" onClick={() => setEditing(false)} disabled={saving}>
              Cancel
            </button>
            {state.lyrics ? (
              <button className="btn btn--danger" type="button" onClick={reset} disabled={saving}>
                Reset to file
              </button>
            ) : null}
          </div>
        </div>
      ) : state.status === "loading" ? (
        <div className="lyrics-panel__empty">Loading…</div>
      ) : state.status === "error" ? (
        <div className="lyrics-panel__empty">Lyrics could not be loaded.</div>
      ) : state.status === "none" || !state.lyrics ? (
        <div className="lyrics-panel__empty">
          <p>No lyrics for this song.</p>
          {working ? <p className="lyrics-panel__hint">Your server is writing them down. A minute or two on a small server.</p> : null}
          {state.generation?.state === "failed" ? <p className="lyrics-panel__hint">{state.generation.reason}</p> : null}
          {state.generation?.state === "off" ? (
            <p className="lyrics-panel__hint">Lyrics generation is off. An admin can turn it on under Settings → Automation.</p>
          ) : null}
          <div className="settings-card__actions">
            {state.generation?.state === "available" || state.generation?.state === "failed" ? (
              <button className="btn btn--primary" type="button" onClick={generate}>
                Generate on your server
              </button>
            ) : null}
            {isAdmin ? (
              <button className="btn" type="button" onClick={startEditing}>
                Add lyrics
              </button>
            ) : null}
          </div>
        </div>
      ) : (
        <>
          <div className="lyrics-panel__list" ref={listRef}>
            {lines.map((line, index) => {
              const isActive = synced && index === activeIndex;
              const className = `lyrics-panel__line${synced ? " lyrics-panel__line--timed" : ""}${
                isActive ? " lyrics-panel__line--active" : ""
              }${synced && index < activeIndex ? " lyrics-panel__line--past" : ""}`;
              return synced ? (
                <button
                  key={`${index}-${line}`}
                  ref={(node) => (lineRefs.current[index] = node)}
                  className={className}
                  type="button"
                  onClick={() => seek(synced[index].t)}
                  aria-current={isActive ? "true" : undefined}
                >
                  {line || " "}
                </button>
              ) : (
                <div key={`${index}-${line}`} className={className}>
                  {line || " "}
                </div>
              );
            })}
          </div>
          <div className="lyrics-panel__footer">
            <span className="lyrics-panel__source">
              {state.lyrics.generated ? <Icon name="sparkle" size={12} /> : null}
              {regenerating ? "Your server is redoing these…" : describeLyricsSource(state.lyrics)}
            </span>
            {isAdmin ? (
              <span className="lyrics-panel__footer-actions">
                {state.lyrics.generated && !regenerating ? (
                  <button className="btn btn--small" type="button" onClick={regenerate} title="Throw these away and let the server try again">
                    Regenerate
                  </button>
                ) : null}
                <button className="btn btn--small" type="button" onClick={startEditing}>
                  Edit
                </button>
              </span>
            ) : null}
          </div>
          {state.lyrics.flags ? (
            <div className="lyrics-panel__footer lyrics-panel__footer--flags">
              <span className="lyrics-panel__source">{describeFlags(state.lyrics.flags)}</span>
              {isAdmin ? (
                <span className="lyrics-panel__footer-actions">
                  <button
                    className="btn btn--small"
                    type="button"
                    onClick={() => markExplicit(state.lyrics.flags.explicit_state === "explicit" ? "clean" : "explicit")}
                    title="Your word stands; the server will not change it"
                  >
                    {state.lyrics.flags.explicit_state === "explicit" ? "Mark clean" : "Mark explicit"}
                  </button>
                </span>
              ) : null}
            </div>
          ) : null}
        </>
      )}
    </aside>
  );
}
