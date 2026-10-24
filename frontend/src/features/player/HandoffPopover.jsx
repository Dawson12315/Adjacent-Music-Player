import { Icon } from "../../components/Icon";
import { statusLine, unpickableReason } from "./handoffLabels";

/** A device's kind as one of the icon set's glyphs. */
function kindIcon(kind) {
  if (kind === "web") return "albums";
  if (kind === "tablet") return "albums";
  return "tracks";
}

/**
 * The "Play on" popover: every device the account has used, the one playing
 * first, each pickable unless it is away. Opens upward from the player bar.
 *
 * Which row is playing comes from the lease (`activeDeviceId`), not from the
 * device rows: the rows are a snapshot that used to arrive once per
 * connection, and a row still marked playing from an hour ago disabled the
 * very device the listener needed. The lease is the live fact.
 */
export function HandoffPopover({ devices = [], activeDeviceId = undefined, onChoose }) {
  const rows = devices.map((device) =>
    activeDeviceId === undefined ? device : { ...device, is_active: device.device_id === activeDeviceId },
  );
  return (
    <div className="menu menu--right menu--up handoff-menu" role="menu">
      <div className="menu__label">Play on</div>
      {rows.length === 0 ? (
        <div className="handoff-menu__empty">No other devices yet. Sign in elsewhere to see it here.</div>
      ) : null}
      {rows.map((device) => {
        const reason = unpickableReason(device);
        const pickable = reason === null;
        return (
          <button
            key={device.device_id}
            className={`menu__item handoff-menu__item ${device.is_active ? "handoff-menu__item--active" : ""}`}
            type="button"
            role="menuitem"
            aria-disabled={!pickable || undefined}
            title={reason || undefined}
            onClick={() => {
              if (pickable) onChoose?.(device.device_id);
            }}
            aria-label={`${device.name}${device.is_this_device ? ", this browser" : ""}. ${statusLine(device)}.${
              pickable ? " Play here." : ` ${reason}.`
            }`}
          >
            <Icon name={kindIcon(device.kind)} size={18} />
            <span className="handoff-menu__text">
              <span className="handoff-menu__name">
                {device.name}
                {device.is_this_device ? "  ·  This browser" : ""}
              </span>
              <span className="handoff-menu__status">{statusLine(device)}</span>
            </span>
            {device.is_active ? <Icon name="handoff" size={16} /> : null}
          </button>
        );
      })}
    </div>
  );
}

export default HandoffPopover;
