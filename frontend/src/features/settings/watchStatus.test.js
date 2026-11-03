import { describe, expect, it } from "vitest";

import { ago, describeWatch } from "./watchStatus";

const NOW = 1_800_000_000_000; // ms
const sec = NOW / 1000;

describe("the folder watcher's status line", () => {
  it("says nothing on an older server, or when the watch is off and nobody asked", () => {
    expect(describeWatch(undefined)).toBeNull();
    expect(describeWatch({ enabled: false, state: "stopped" })).toBeNull();
    expect(describeWatch({ enabled: false, state: "stopped" }, { wanted: false })).toBeNull();
  });

  it("asks for a save while the checkbox is ahead of the server", () => {
    expect(describeWatch({ enabled: false, state: "stopped" }, { wanted: true }).text).toBe("Save settings to start watching.");
    expect(describeWatch({ enabled: true, state: "watching" }, { wanted: false }).text).toBe("Save settings to stop watching.");
  });

  it("reads watching, with the last pickup", () => {
    const quiet = describeWatch({ enabled: true, state: "watching", mode: "events" }, { wanted: true, now: NOW });
    expect(quiet).toEqual({ tone: "ok", text: "Watching the folder" });

    const picked = describeWatch(
      { enabled: true, state: "watching", mode: "events", last_import_at: sec - 240, last_added: 12 },
      { wanted: true, now: NOW },
    );
    expect(picked.text).toBe("Watching the folder · picked up 12 tracks 4 min ago");

    const nothing = describeWatch(
      { enabled: true, state: "watching", mode: "events", last_import_at: sec - 30, last_added: 0 },
      { now: NOW },
    );
    expect(nothing.text).toBe("Watching the folder · last import just now, nothing new");

    const landing = describeWatch({ enabled: true, state: "watching", mode: "events", pending: 3 }, { now: NOW });
    expect(landing.text).toBe("Watching the folder · 3 files landing");
  });

  it("says so when it is polling, and why", () => {
    const polling = describeWatch(
      { enabled: true, state: "watching", mode: "polling", poll_seconds: 120 },
      { now: NOW },
    );
    expect(polling.tone).toBe("warn");
    expect(polling.text).toBe("Checking the folder every 2 minutes — this storage does not report changes");
  });

  it("shows an error without hiding that the daily scan still runs", () => {
    const broken = describeWatch({ enabled: true, state: "error", error: "No space left on device" });
    expect(broken.tone).toBe("warn");
    expect(broken.text).toContain("No space left on device");
    expect(broken.text).toContain("the daily scan still runs");
    expect(describeWatch({ enabled: true, state: "starting" }).text).toBe("Starting the watcher…");
  });

  it("counts time in the units a person would", () => {
    expect(ago(sec - 5, NOW)).toBe("just now");
    expect(ago(sec - 125, NOW)).toBe("2 min ago");
    expect(ago(sec - 3700, NOW)).toBe("1 hour ago");
    expect(ago(sec - 2 * 86400, NOW)).toBe("2 days ago");
  });
});
