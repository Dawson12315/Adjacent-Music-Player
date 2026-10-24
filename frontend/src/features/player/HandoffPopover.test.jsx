import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { HandoffPopover } from "./HandoffPopover";

const rows = [
  { device_id: "phone", name: "Phone", kind: "phone", online: true, is_active: true, is_this_device: false },
  { device_id: "web", name: "Chrome on Mac", kind: "web", online: true, is_active: false, is_this_device: true },
  { device_id: "old", name: "Old tablet", kind: "tablet", online: false, is_active: false, last_seen_at: "2026-01-01T00:00:00Z" },
];

describe("the Play on popover", () => {
  it("marks the holder from the lease, not from the device rows", () => {
    // The rows still say the phone is playing (a stale snapshot); the lease
    // says this browser took it. The lease wins, and the phone is pickable.
    const onChoose = vi.fn();
    render(<HandoffPopover devices={rows} activeDeviceId="web" onChoose={onChoose} />);

    expect(screen.getByRole("menuitem", { name: /Chrome on Mac, this browser. Playing now. Already playing here/ })).toBeInTheDocument();
    const phone = screen.getByRole("menuitem", { name: /Phone. Ready. Play here/ });
    fireEvent.click(phone);
    expect(onChoose).toHaveBeenCalledWith("phone");
  });

  it("gives every row it will not pick a reason, and ignores clicks on it", () => {
    const onChoose = vi.fn();
    render(<HandoffPopover devices={rows} activeDeviceId="phone" onChoose={onChoose} />);

    const holder = screen.getByRole("menuitem", { name: /Phone. Playing now. Already playing here/ });
    expect(holder).toHaveAttribute("aria-disabled", "true");
    fireEvent.click(holder);
    const away = screen.getByRole("menuitem", { name: /Old tablet. Last seen .*Not reachable right now/ });
    expect(away).toHaveAttribute("title", "Not reachable right now");
    fireEvent.click(away);
    expect(onChoose).not.toHaveBeenCalled();
  });

  it("falls back to the rows when no lease is given", () => {
    render(<HandoffPopover devices={rows} onChoose={() => {}} />);
    expect(screen.getByRole("menuitem", { name: /Phone. Playing now/ })).toHaveAttribute("aria-disabled", "true");
  });
});
