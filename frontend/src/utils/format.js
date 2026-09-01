/** Seconds to `m:ss`. Guards against the NaN duration an unloaded audio element reports. */
export function formatTime(timeInSeconds) {
  if (!Number.isFinite(timeInSeconds)) {
    return "0:00";
  }

  const safeSeconds = Math.max(0, timeInSeconds);
  const minutes = Math.floor(safeSeconds / 60);
  const seconds = Math.floor(safeSeconds % 60);

  return `${minutes}:${seconds.toString().padStart(2, "0")}`;
}
