import { describe, expect, it } from "vitest";

import {
  DEFAULT_THEME,
  THEMES,
  THEME_IDS,
  dayLineFor,
  effectiveTheme,
  isThemeId,
  nextMidnight,
  themeById,
  themeForDate,
  windowLabel,
} from "./themes";

const d = (month, day, year = 2026) => new Date(year, month - 1, day, 12);

describe("the catalogue", () => {
  it("has thirteen themes, Adjacent first and default, no green among them", () => {
    expect(THEMES).toHaveLength(13);
    expect(THEME_IDS[0]).toBe("adjacent");
    expect(DEFAULT_THEME).toBe("adjacent");
    expect(isThemeId("halloween")).toBe(true);
    expect(isThemeId("green")).toBe(false);
    expect(isThemeId("stpatricks")).toBe(false);
    expect(themeById("nope").id).toBe("adjacent");
    expect(windowLabel(themeById("halloween"))).toBe("24 Oct – 31 Oct");
    expect(windowLabel(themeById("ember"))).toBe("");
  });
});

describe("themeForDate", () => {
  it("covers the whole year with the four seasons", () => {
    expect(themeForDate(d(1, 15)).id).toBe("winter");
    expect(themeForDate(d(3, 19)).id).toBe("winter");
    expect(themeForDate(d(3, 20)).id).toBe("spring");
    expect(themeForDate(d(6, 20)).id).toBe("spring");
    expect(themeForDate(d(6, 21)).id).toBe("summer");
    expect(themeForDate(d(9, 21)).id).toBe("summer");
    expect(themeForDate(d(9, 22)).id).toBe("autumn");
    expect(themeForDate(d(11, 30)).id).toBe("autumn");
    expect(themeForDate(d(12, 1)).id).toBe("winter");
  });

  it("lets a holiday take over its season, and hands back after", () => {
    expect(themeForDate(d(10, 23)).id).toBe("autumn");
    expect(themeForDate(d(10, 24)).id).toBe("halloween");
    expect(themeForDate(d(10, 31)).id).toBe("halloween");
    expect(themeForDate(d(11, 1)).id).toBe("autumn");
    expect(themeForDate(d(12, 13)).id).toBe("winter");
    expect(themeForDate(d(12, 14)).id).toBe("festive");
    expect(themeForDate(d(12, 26)).id).toBe("festive");
    expect(themeForDate(d(12, 27)).id).toBe("winter");
    expect(themeForDate(d(12, 31)).id).toBe("newyear");
    expect(themeForDate(d(1, 1)).id).toBe("newyear");
    expect(themeForDate(d(1, 2)).id).toBe("winter");
    expect(themeForDate(d(2, 9)).id).toBe("winter");
    expect(themeForDate(d(2, 10)).id).toBe("valentine");
    expect(themeForDate(d(2, 14)).id).toBe("valentine");
    expect(themeForDate(d(2, 15)).id).toBe("winter");
  });

  it("moves the seasons six months south, and leaves the holidays where they are", () => {
    expect(themeForDate(d(1, 15), { southern: true }).id).toBe("summer");
    expect(themeForDate(d(7, 15), { southern: true }).id).toBe("winter");
    expect(themeForDate(d(4, 10), { southern: true }).id).toBe("autumn");
    expect(themeForDate(d(10, 10), { southern: true }).id).toBe("spring");
    expect(themeForDate(d(10, 31), { southern: true }).id).toBe("halloween");
    expect(themeForDate(d(12, 25), { southern: true }).id).toBe("festive");
  });
});

describe("effectiveTheme", () => {
  it("is the chosen theme unless the seasons are followed", () => {
    expect(effectiveTheme({ theme: "ember" }, d(10, 31)).id).toBe("ember");
    expect(effectiveTheme({ theme: "ember", seasonal: true }, d(10, 31)).id).toBe("halloween");
    expect(effectiveTheme({}, d(10, 31)).id).toBe("adjacent");
    expect(effectiveTheme({ theme: "adjacent", seasonal: true, southern: true }, d(1, 15)).id).toBe("summer");
  });
});

describe("the day line and the clock", () => {
  it("speaks on the day only", () => {
    expect(dayLineFor(d(10, 31))).toBe("Happy Halloween.");
    expect(dayLineFor(d(10, 30))).toBe("");
    expect(dayLineFor(d(12, 31))).toBe("Happy New Year.");
    expect(dayLineFor(d(1, 1))).toBe("Happy New Year.");
    expect(dayLineFor(d(2, 14))).toBe("Happy Valentine's Day.");
    expect(dayLineFor(d(2, 13))).toBe("");
  });

  it("knows the next local midnight", () => {
    const at = new Date(2026, 9, 31, 22, 15);
    const next = nextMidnight(at);
    expect(next.getDate()).toBe(1);
    expect(next.getMonth()).toBe(10);
    expect(next.getHours()).toBe(0);
  });
});
