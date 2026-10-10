import { useState } from "react";

import { getDeviceId, getDeviceName, setDeviceNameOverride } from "../../services/deviceIdentity";

/**
 * What this browser calls itself in the "Play on" picker. Self-contained: it
 * reads and writes the device identity directly, so the settings view needs
 * nothing threaded in for it.
 */
export function ThisBrowserPanel() {
  const [name, setName] = useState(() => getDeviceName());
  const [idTail] = useState(() => getDeviceId().slice(0, 8));
  const [saved, setSaved] = useState(false);

  const save = () => {
    setDeviceNameOverride(name);
    setName(getDeviceName());
    setSaved(true);
  };

  return (
    <section className="settings-section">
      <div className="settings-section__header">
        <h2 className="settings-section__title">This browser</h2>
      </div>
      <div className="settings-card">
        <div className="settings-card__text">
          The name your other devices show in the Play on picker. A new name
          takes effect the next time this browser connects.
        </div>
        <input
          className="input"
          value={name}
          maxLength={80}
          onChange={(event) => {
            setName(event.target.value);
            setSaved(false);
          }}
          aria-label="This browser's name"
          placeholder="This browser's name"
        />
        <div className="settings-card__actions">
          <button className="btn btn--primary" type="button" onClick={save}>
            {saved ? "Saved" : "Save name"}
          </button>
        </div>
        {idTail ? <div className="settings-card__text">Device id {idTail}</div> : null}
      </div>
    </section>
  );
}

export default ThisBrowserPanel;
