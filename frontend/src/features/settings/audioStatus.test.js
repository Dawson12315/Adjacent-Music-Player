import { describe, expect, it } from "vitest";

import { describeAudioStatus, describeCoverage } from "./audioStatus";

const STATUS = {
  tracks: 36534,
  profiled: 12000,
  flagged: 9000,
  vocal: 8000,
  instrumental: 1000,
  languages: { en: 7000, es: 1000 },
  explicit: 340,
  analysis: { enabled: true, available: { sound: true, flags: true }, is_running: false, queued: 0, done: 0 },
};

describe("the audio analysis status line", () => {
  it("says nothing before the first read", () => {
    expect(describeAudioStatus(null, true)).toBeNull();
  });

  it("reports coverage and readiness", () => {
    const line = describeAudioStatus(STATUS, true);
    expect(line.tone).toBe("ok");
    expect(line.text).toContain("12,000 of 36,534 tracks profiled, 9,000 flagged");
    expect(line.text).toContain("Ready");
  });

  it("says when the server cannot analyse at all, and when only the sound half can run", () => {
    const none = describeAudioStatus({ ...STATUS, analysis: { ...STATUS.analysis, available: { sound: false, flags: false } } }, true);
    expect(none.tone).toBe("warn");
    const soundOnly = describeAudioStatus({ ...STATUS, analysis: { ...STATUS.analysis, available: { sound: true, flags: false } } }, true);
    expect(soundOnly.text).toContain("Language and vocal flags need the lyrics model runtime");
  });

  it("tells the admin to save when the switch and the server disagree", () => {
    expect(describeAudioStatus(STATUS, false).text).toContain("Save settings to turn analysis off");
    expect(describeAudioStatus({ ...STATUS, analysis: { ...STATUS.analysis, enabled: false } }, true).text).toContain("Save settings to turn analysis on");
  });

  it("shows the worker at work, and the last error", () => {
    expect(describeAudioStatus({ ...STATUS, analysis: { ...STATUS.analysis, is_running: true, queued: 12 } }, true).text).toContain("Listening to a track now, 12 waiting");
    expect(describeAudioStatus({ ...STATUS, analysis: { ...STATUS.analysis, last_error: "ffmpeg could not decode the file" } }, true).tone).toBe("warn");
  });

  it("summarises what was found", () => {
    expect(describeCoverage(STATUS)).toBe("8,000 vocal · 1,000 instrumental · 2 languages · 340 explicit");
    expect(describeCoverage({ tracks: 10 })).toBeNull();
  });
});
