/**
 * Green is the one colour the brand does not wear. Every theme palette —
 * in the catalogue and in tokens.css — is read here and refused if any
 * colour sits in the green arc. The single exception is the `--success`
 * status token, which is pinned by value and is not a theme's to change.
 */
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

import { THEMES } from "./themes";

// Read as a file, not imported: Vite would hand the test the processed stylesheet.
const tokens = readFileSync(resolve(globalThis.process.cwd(), "src/styles/tokens.css"), "utf8");

function hexToHsl(hex) {
  const value = hex.replace("#", "");
  const full = value.length === 3 ? value.split("").map((c) => c + c).join("") : value;
  const r = parseInt(full.slice(0, 2), 16) / 255;
  const g = parseInt(full.slice(2, 4), 16) / 255;
  const b = parseInt(full.slice(4, 6), 16) / 255;
  const max = Math.max(r, g, b);
  const min = Math.min(r, g, b);
  const l = (max + min) / 2;
  const delta = max - min;
  if (delta === 0) return { h: 0, s: 0, l };
  const s = delta / (1 - Math.abs(2 * l - 1));
  let h;
  if (max === r) h = ((g - b) / delta) % 6;
  else if (max === g) h = (b - r) / delta + 2;
  else h = (r - g) / delta + 4;
  h = (h * 60 + 360) % 360;
  return { h, s, l };
}

/** The forbidden arc: lime through teal (70°–185°), at any saturation worth seeing. */
export function isGreen(hex) {
  const { h, s } = hexToHsl(hex);
  return h >= 70 && h <= 185 && s > 0.12;
}

const HEX = /#[0-9a-fA-F]{6}\b/g;

describe("never green", () => {
  it("has no green in the catalogue's accents or grounds", () => {
    for (const theme of THEMES) {
      expect(isGreen(theme.accent), `${theme.id} accent ${theme.accent}`).toBe(false);
      expect(isGreen(theme.ground), `${theme.id} ground ${theme.ground}`).toBe(false);
    }
  });

  it("has no green in any theme block of tokens.css", () => {
    const blocks = [...tokens.matchAll(/:root\[data-theme="([a-z]+)"\]\s*\{([^}]*)\}/g)];
    expect(blocks.length).toBe(THEMES.length - 1);
    for (const [, id, body] of blocks) {
      for (const hex of body.match(HEX) || []) {
        expect(isGreen(hex), `${id}: ${hex}`).toBe(false);
      }
    }
  });

  it("keeps the one status green exactly where it is, and nowhere a theme can reach", () => {
    expect(tokens).toMatch(/--success:\s*#3DD68C;/);
    const base = tokens.split(':root[data-theme="')[0];
    const greens = (base.match(HEX) || []).filter(isGreen);
    expect(greens).toEqual(["#3DD68C"]);
    for (const [, id, body] of tokens.matchAll(/:root\[data-theme="([a-z]+)"\]\s*\{([^}]*)\}/g)) {
      expect(body.includes("--success"), `${id} redefines --success`).toBe(false);
    }
  });

  it("knows green when it sees it", () => {
    expect(isGreen("#3DD68C")).toBe(true);
    expect(isGreen("#22C55E")).toBe(true);
    expect(isGreen("#14B8A6")).toBe(true);
    expect(isGreen("#FFC93C")).toBe(false);
    expect(isGreen("#2F7CFF")).toBe(false);
    expect(isGreen("#3FA7FF")).toBe(false);
    expect(isGreen("#6F7788")).toBe(false);
  });
});
