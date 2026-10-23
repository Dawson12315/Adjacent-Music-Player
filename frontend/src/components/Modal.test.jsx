import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";

import { Modal } from "./Modal";

/** A parent that re-renders on every keystroke and passes onClose inline, as ServerPanel does. */
function ConfirmDialog({ onClose }) {
  const [word, setWord] = useState("");
  return (
    <Modal title="Confirm" onClose={() => onClose(word)}>
      <label>
        Type migrate to confirm
        <input value={word} onChange={(event) => setWord(event.target.value)} />
      </label>
    </Modal>
  );
}

describe("Modal", () => {
  it("keeps focus in the field while the parent re-renders on every keystroke", async () => {
    const user = userEvent.setup();
    render(<ConfirmDialog onClose={vi.fn()} />);

    const input = screen.getByLabelText("Type migrate to confirm");
    await user.click(input);
    await user.type(input, "migrate");

    expect(input).toHaveValue("migrate");
    expect(document.activeElement).toBe(input);
  });

  it("closes on Escape with the latest handler, not the one from mount", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    render(<ConfirmDialog onClose={onClose} />);

    const input = screen.getByLabelText("Type migrate to confirm");
    await user.click(input);
    await user.type(input, "mig");
    await user.keyboard("{Escape}");

    expect(onClose).toHaveBeenCalledWith("mig");
  });

  it("moves focus in on open", () => {
    render(
      <Modal title="Plain" onClose={() => {}}>
        <button type="button">First</button>
      </Modal>,
    );
    expect(document.activeElement?.getAttribute("aria-label")).toBe("Close");
  });
});
