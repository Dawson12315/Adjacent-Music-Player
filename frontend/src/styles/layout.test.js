import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

// Read from disk rather than imported: vitest stubs CSS imports, so `?raw`
// hands back an empty string. Resolved from the project root because
// `import.meta.url` is an http:// URL under jsdom, and reached through
// `globalThis` because `process` is not a global in a browser lint config.
const CSS_PATH = resolve(globalThis.process.cwd(), "src/styles/layout.css");
const css = existsSync(CSS_PATH) ? readFileSync(CSS_PATH, "utf8") : "";

/**
 * The sidebar must not let its children shrink.
 *
 * It is a flex column that scrolls, and flex children default to
 * `flex-shrink: 1`. Once the playlists outgrew the viewport the browser squashed
 * their *box* while the rows inside kept their height: they spilled out and drew
 * over Insights, Settings and the library stats, and because the box had not
 * grown, `overflow-y` had nothing to scroll. With enough playlists the bottom of
 * the nav simply could not be reached.
 *
 * There is no runtime test for this. jsdom does no layout, so every unit test
 * passes either way; it only appears in a real browser, with enough playlists to
 * overflow, which is why it shipped. This asserts the two declarations the fix
 * depends on so removing one fails here instead of in someone's sidebar.
 */
describe("sidebar layout", () => {
  it("found the stylesheet", () => {
    // Guard the guard: an unreadable file would make every check below vacuous.
    expect(css.length, `expected to read ${CSS_PATH}`).toBeGreaterThan(0);
  });

  const block = (selector) => {
    const at = css.indexOf(selector + " {");
    expect(at, `${selector} should exist in layout.css`).toBeGreaterThan(-1);
    return css.slice(at, css.indexOf("}", at));
  };

  it("scrolls rather than clipping", () => {
    expect(block(".sidebar")).toMatch(/overflow-y:\s*auto/);
  });

  it("holds every child at its natural height", () => {
    // Without this the sidebar's scroll height is a lie and the tail of the nav
    // becomes unreachable.
    expect(block(".sidebar > *")).toMatch(/flex:\s*none/);
  });
});
