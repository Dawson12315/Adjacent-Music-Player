import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

/**
 * How the API origin is resolved from runtime config.
 *
 * The case that matters here is the reverse-proxy deployment, where the app and
 * the API share one hostname. That could not be expressed at all: an empty
 * value fell through to a port-8000 guess, so a site on https://example.com
 * pointed its API at https://example.com:8000 — or, if someone set a LAN IP
 * instead, at an address unreachable from outside and blocked as mixed content.
 * Both present as requests that hang rather than as an error.
 */

async function resolveWith(configured) {
  vi.resetModules();

  if (configured === undefined) {
    delete window.APP_CONFIG;
  } else {
    window.APP_CONFIG = { API_BASE_URL: configured };
  }

  const { API_BASE_URL } = await import("./config.js");
  return API_BASE_URL;
}


function setProtocol(protocol) {
  // jsdom's location is read-only; redefine just the protocol for the test.
  Object.defineProperty(window, "location", {
    configurable: true,
    value: { ...window.location, protocol, hostname: window.location.hostname },
  });
}

describe("API_BASE_URL", () => {
  const original = window.APP_CONFIG;

  beforeEach(() => {
    delete window.APP_CONFIG;
  });

  afterEach(() => {
    window.APP_CONFIG = original;
  });

  it('treats "/" as same origin', async () => {
    // Behind a reverse proxy the API is served from the same hostname, so the
    // right base is no base at all — relative URLs.
    expect(await resolveWith("/")).toBe("");
  });

  it("falls back to the LAN two-port layout over plain HTTP", async () => {
    // The layout this fallback was written for: frontend on :5173, backend on
    // :8000, no TLS.
    setProtocol("http:");

    expect(await resolveWith(undefined)).toBe(
      `http://${window.location.hostname}:8000`
    );
    expect(await resolveWith("")).toBe(
      `http://${window.location.hostname}:8000`
    );
  });

  it("assumes same origin over HTTPS when config.js did not arrive", async () => {
    // Serving over TLS means a proxy is in front, and no proxy publishes the
    // backend on :8000 of the public hostname — a CDN does not even answer
    // there, so the old guess failed as a hang rather than as an error.
    setProtocol("https:");

    expect(await resolveWith(undefined)).toBe("");
    expect(await resolveWith("")).toBe("");
  });

  it("keeps an explicit origin", async () => {
    expect(await resolveWith("http://192.168.1.10:8000")).toBe(
      "http://192.168.1.10:8000"
    );
  });

  it("tolerates a trailing slash on an explicit origin", async () => {
    // Every path this is joined to already starts with one; without the strip
    // the result carries a doubled slash.
    expect(await resolveWith("https://example.com/")).toBe("https://example.com");
    expect(await resolveWith("https://example.com///")).toBe("https://example.com");
  });

  it("ignores surrounding whitespace", async () => {
    // Docker interpolation and hand-edited compose files both produce this.
    expect(await resolveWith("  https://example.com  ")).toBe("https://example.com");
  });
});
