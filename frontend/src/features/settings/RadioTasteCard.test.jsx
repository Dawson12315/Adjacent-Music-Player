import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

const radio = vi.hoisted(() => ({
  getRadioTaste: vi.fn(),
  resetRadioTaste: vi.fn(),
}));
vi.mock("../../services/radioService", () => radio);
vi.mock("../../contexts/AuthContext", () => ({ useAuth: () => ({ currentUser: { username: "d" } }) }));

import { RadioTasteCard } from "./AccountPanel";

afterEach(() => {
  radio.getRadioTaste.mockReset();
  radio.resetRadioTaste.mockReset();
});

describe("the radio taste card", () => {
  it("says what the thumbs have built up and resets it", async () => {
    radio.getRadioTaste.mockResolvedValue({ artists: 3, votes_up: 4, votes_down: 2 });
    radio.resetRadioTaste.mockResolvedValue({ artists: 0, votes_up: 0, votes_down: 0, cleared: 3 });
    render(<RadioTasteCard />);
    expect(await screen.findByText(/6 votes have nudged 3 artists/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Reset radio taste" }));
    await waitFor(() => expect(radio.resetRadioTaste).toHaveBeenCalledTimes(1));
    expect(await screen.findByText(/Nothing yet/)).toBeTruthy();
    expect(screen.getByRole("button", { name: "Reset radio taste" }).disabled).toBe(true);
  });

  it("is not there on a server without a map", async () => {
    radio.getRadioTaste.mockRejectedValue(new Error("404"));
    const { container } = render(<RadioTasteCard />);
    await waitFor(() => expect(radio.getRadioTaste).toHaveBeenCalled());
    expect(container.querySelector("[data-testid='radio-taste']")).toBeNull();
  });
});
