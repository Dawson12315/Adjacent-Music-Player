import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { mocks } = vi.hoisted(() => ({
  mocks: {
    user: { id: 1, username: "dawson", theme: "adjacent", theme_seasonal: false, theme_southern: false },
    updatePreferences: vi.fn(async (body) => body),
    notify: vi.fn(),
  },
}));
vi.mock("./AuthContext", () => ({ useAuth: () => ({ currentUser: mocks.user, updatePreferences: mocks.updatePreferences }) }));
vi.mock("./NotificationContext", () => ({ useNotifications: () => ({ notify: mocks.notify }) }));

import { ThemeProvider } from "./ThemeProvider";
import { useTheme } from "./ThemeContext";

// A real storage for the test: the environment's may be a stub without the methods.
const memory = new Map();
vi.stubGlobal("localStorage", {
  getItem: (key) => (memory.has(key) ? memory.get(key) : null),
  setItem: (key, value) => memory.set(key, String(value)),
  removeItem: (key) => memory.delete(key),
  clear: () => memory.clear(),
});

function Probe() {
  const theming = useTheme();
  return <output data-testid="theme">{theming.theme.id}:{theming.dress || "-"}</output>;
}

const at = (iso) => new Date(iso);

beforeEach(() => {
  localStorage.clear();
  document.documentElement.removeAttribute("data-theme");
  mocks.notify.mockClear();
  mocks.user = { id: 1, username: "dawson", theme: "adjacent", theme_seasonal: false, theme_southern: false };
});
afterEach(() => {
  vi.useRealTimers();
});

describe("the theme provider", () => {
  it("wears Adjacent by default and sets nothing on the page", () => {
    render(<ThemeProvider now={() => at("2026-10-31T12:00:00")}><Probe /></ThemeProvider>);
    expect(screen.getByTestId("theme").textContent).toBe("adjacent:-");
    expect(document.documentElement.hasAttribute("data-theme")).toBe(false);
    expect(localStorage.getItem("adjacent.theme")).toBeNull();
    expect(mocks.notify).not.toHaveBeenCalled();
  });

  it("wears the chosen theme all year, and remembers it for the next first paint", () => {
    mocks.user = { ...mocks.user, theme: "ember" };
    render(<ThemeProvider now={() => at("2026-10-31T12:00:00")}><Probe /></ThemeProvider>);
    expect(document.documentElement.dataset.theme).toBe("ember");
    expect(localStorage.getItem("adjacent.theme")).toBe("ember");
    expect(screen.getByTestId("theme").textContent).toBe("ember:-");
  });

  it("lets the calendar take over when the seasons are followed, says so once, and dresses the duck", () => {
    mocks.user = { ...mocks.user, theme: "ember", theme_seasonal: true };
    const { unmount } = render(<ThemeProvider now={() => at("2026-10-31T12:00:00")}><Probe /></ThemeProvider>);
    expect(document.documentElement.dataset.theme).toBe("halloween");
    expect(screen.getByTestId("theme").textContent).toBe("halloween:witch");
    expect(mocks.notify).toHaveBeenCalledTimes(1);
    expect(mocks.notify.mock.calls[0][0]).toContain("Halloween");
    unmount();
    // The same window again: nothing more to say.
    render(<ThemeProvider now={() => at("2026-10-31T18:00:00")}><Probe /></ThemeProvider>);
    expect(mocks.notify).toHaveBeenCalledTimes(1);
  });

  it("turns at local midnight while the tab is open", () => {
    vi.useFakeTimers();
    let clock = at("2026-10-31T23:59:30");
    mocks.user = { ...mocks.user, theme_seasonal: true };
    render(<ThemeProvider now={() => clock}><Probe /></ThemeProvider>);
    expect(document.documentElement.dataset.theme).toBe("halloween");
    clock = at("2026-11-01T00:00:01");
    act(() => {
      vi.advanceTimersByTime(60 * 1000);
    });
    expect(document.documentElement.dataset.theme).toBe("autumn");
    expect(document.documentElement.hasAttribute("data-theme-fading")).toBe(true);
    act(() => {
      vi.advanceTimersByTime(1000);
    });
    expect(document.documentElement.hasAttribute("data-theme-fading")).toBe(false);
  });

  it("saves a pick through the account", async () => {
    let api;
    function Grab() {
      // eslint-disable-next-line react-hooks/globals -- the test drives the provider through its context
      api = useTheme();
      return null;
    }
    render(<ThemeProvider now={() => at("2026-05-01T12:00:00")}><Grab /></ThemeProvider>);
    await act(async () => {
      await api.setPreferences({ theme: "rosewood", seasonal: true, southern: true });
    });
    expect(mocks.updatePreferences).toHaveBeenCalledWith({ theme: "rosewood", theme_seasonal: true, theme_southern: true });
  });
});
