import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { theming } = vi.hoisted(() => ({
  theming: {
    theme: { id: "halloween", name: "Halloween", kind: "holiday", dress: "witch" },
    prefs: { theme: "ember", seasonal: true, southern: false },
    calendarTheme: { id: "halloween", name: "Halloween" },
    setPreferences: vi.fn(() => Promise.resolve({})),
  },
}));
vi.mock("../../contexts/ThemeContext", () => ({ ThemeContext: { Provider: ({ children }) => children }, useTheme: () => theming }));

import { AppearancePanel } from "./AppearancePanel";

beforeEach(() => theming.setPreferences.mockClear());

describe("Settings → Appearance", () => {
  it("shows the thirteen, marks the pick, and saves a new one through the account", async () => {
    render(<AppearancePanel />);
    const swatches = screen.getAllByRole("button", { pressed: false }).concat(screen.getAllByRole("button", { pressed: true }));
    expect(swatches.filter((b) => b.classList.contains("theme-swatch"))).toHaveLength(13);
    expect(screen.getByRole("button", { name: /^Ember/ })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: /^Halloween, 24 Oct – 31 Oct/ })).toHaveAttribute("aria-pressed", "false");

    fireEvent.click(screen.getByRole("button", { name: /^Rosewood/ }));
    await waitFor(() => expect(theming.setPreferences).toHaveBeenCalledWith({ theme: "rosewood" }));
  });

  it("switches the seasons and the hemisphere, and says what is worn", async () => {
    render(<AppearancePanel />);
    const follow = screen.getByRole("switch", { name: "Follow the seasons" });
    expect(follow).toHaveAttribute("aria-checked", "true");
    fireEvent.click(follow);
    await waitFor(() => expect(theming.setPreferences).toHaveBeenCalledWith({ seasonal: false }));
    // One save at a time: the second switch waits for the first to land.
    await waitFor(() => expect(screen.getByRole("switch", { name: "Seasons as in the southern hemisphere" })).not.toBeDisabled());
    fireEvent.click(screen.getByRole("switch", { name: "Seasons as in the southern hemisphere" }));
    await waitFor(() => expect(theming.setPreferences).toHaveBeenCalledWith({ southern: true }));
    expect(screen.getByText(/Wearing/).textContent).toContain("Halloween for the season, over Ember");
    expect(screen.getByText(/Right now the calendar would wear/).textContent).toContain("Halloween");
  });
});
