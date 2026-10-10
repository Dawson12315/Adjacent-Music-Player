import { Icon } from "../../components/Icon";
import { statusLine } from "./handoffLabels";

/** A device's kind as one of the icon set's glyphs. */
function kindIcon(kind) {
  if (kind === "web") return "albums";
  if (kind === "tablet") return "albums";
  return "tracks";
}

/**
 * The "Play on" popover: every device the account has used, the one playing
 * first, each pickable unless it is away. Opens upward from the player bar.
 */
export function HandoffPopover({ devices = [], onChoose }) {
  return (
    <div className="menu menu--right menu--up handoff-menu" role="menu">
      <div className="menu__label">Play on</div>
      {devices.length === 0 ? (
        <div className="handoff-menu__empty">No other devices yet. Sign in elsewhere to see it here.</div>
      ) : null}
      {devices.map((device) => {
        const pickable = device.online && !device.is_active;
        return (
          <button
            key={device.device_id}
            className={`menu__item handoff-menu__item ${device.is_active ? "handoff-menu__item--active" : ""}`}
            type="button"
            role="menuitem"
            disabled={!pickable}
            onClick={() => onChoose?.(device.device_id)}
            aria-label={`${device.name}${device.is_this_device ? ", this browser" : ""}. ${statusLine(device)}.${
              pickable ? " Play here." : ""
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
