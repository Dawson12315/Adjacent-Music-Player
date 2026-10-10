/** Plain-words status for a handoff device row, apart from the component so
 *  it can be tested and the popover stays a components-only module. */

/** "Last seen 10 min ago", from an ISO timestamp. */
export function lastSeenLabel(iso, nowMs = Date.now()) {
  if (!iso) return "Offline";
  const then = Date.parse(iso);
  if (!Number.isFinite(then)) return "Offline";
  const mins = Math.max(0, Math.round((nowMs - then) / 60000));
  if (mins < 1) return "Just now";
  if (mins === 1) return "Last seen 1 min ago";
  if (mins < 60) return `Last seen ${mins} min ago`;
  const hrs = Math.round(mins / 60);
  return hrs === 1 ? "Last seen 1 hr ago" : `Last seen ${hrs} hr ago`;
}

export function statusLine(device) {
  if (device.is_active) return device.context === "carplay" ? "Playing now · CarPlay" : "Playing now";
  if (device.online) return device.context === "carplay" ? "Ready · CarPlay" : "Ready";
  return lastSeenLabel(device.last_seen_at);
}
