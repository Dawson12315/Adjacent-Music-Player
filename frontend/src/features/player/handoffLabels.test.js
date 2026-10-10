import { describe, expect, it } from "vitest";

import { lastSeenLabel, statusLine } from "./handoffLabels";

describe("handoff device labels", () => {
  it("says how long ago a device was seen", () => {
    const now = Date.parse("2026-01-01T12:00:00Z");
    expect(lastSeenLabel(new Date(now - 20_000).toISOString(), now)).toBe("Just now");
    expect(lastSeenLabel(new Date(now - 60_000).toISOString(), now)).toBe("Last seen 1 min ago");
    expect(lastSeenLabel(new Date(now - 10 * 60_000).toISOString(), now)).toBe("Last seen 10 min ago");
    expect(lastSeenLabel(new Date(now - 2 * 3_600_000).toISOString(), now)).toBe("Last seen 2 hr ago");
    expect(lastSeenLabel(null)).toBe("Offline");
  });

  it("describes a device's status", () => {
    expect(statusLine({ is_active: true })).toBe("Playing now");
    expect(statusLine({ is_active: true, context: "carplay" })).toBe("Playing now · CarPlay");
    expect(statusLine({ online: true })).toBe("Ready");
    const now = Date.parse("2026-01-01T12:00:00Z");
    expect(statusLine({ online: false, last_seen_at: new Date(now - 5 * 60_000).toISOString() })).toMatch(/Last seen/);
  });
});
