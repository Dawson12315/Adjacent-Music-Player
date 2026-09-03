import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError, onUnauthorized, request } from "./apiClient";

function jsonResponse(body, { status = 200 } = {}) {
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: new Headers({ "content-type": "application/json" }),
    json: async () => body,
    text: async () => JSON.stringify(body),
  };
}

describe("apiClient", () => {
  beforeEach(() => {
    globalThis.fetch = vi.fn();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("always sends cookies, since auth is cookie-based end to end", async () => {
    globalThis.fetch.mockResolvedValue(jsonResponse({ ok: true }));

    await request("/api/tracks");

    expect(globalThis.fetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/tracks"),
      expect.objectContaining({ credentials: "include" }),
    );
  });

  it("serialises a plain object as JSON and sets the content type", async () => {
    globalThis.fetch.mockResolvedValue(jsonResponse({}));

    await request("/api/playlists", { method: "POST", body: { name: "Road trip" } });

    const [, options] = globalThis.fetch.mock.calls[0];

    expect(options.body).toBe(JSON.stringify({ name: "Road trip" }));
    expect(options.headers["Content-Type"]).toBe("application/json");
  });

  it("passes FormData through untouched so the browser sets the boundary", async () => {
    globalThis.fetch.mockResolvedValue(jsonResponse({}));

    const formData = new FormData();
    formData.append("file", new Blob(["x"]), "art.png");

    await request("/api/albums/x/artwork", { method: "POST", body: formData });

    const [, options] = globalThis.fetch.mock.calls[0];

    expect(options.body).toBe(formData);
    expect(options.headers["Content-Type"]).toBeUndefined();
  });

  it("drops null and undefined query parameters", async () => {
    globalThis.fetch.mockResolvedValue(jsonResponse([]));

    await request("/api/tracks", {
      params: { limit: 50, search: null, section: undefined, offset: 0 },
    });

    const [url] = globalThis.fetch.mock.calls[0];

    expect(url).toContain("limit=50");
    expect(url).toContain("offset=0");
    expect(url).not.toContain("search");
    expect(url).not.toContain("section");
  });

  it("surfaces FastAPI's string detail as the error message", async () => {
    globalThis.fetch.mockResolvedValue(
      jsonResponse({ detail: "Playlist already exists" }, { status: 400 }),
    );

    await expect(request("/api/playlists")).rejects.toMatchObject({
      name: "ApiError",
      status: 400,
      message: "Playlist already exists",
    });
  });

  it("flattens a 422 validation detail list into one message", async () => {
    globalThis.fetch.mockResolvedValue(
      jsonResponse(
        { detail: [{ msg: "field required" }, { msg: "value is not valid" }] },
        { status: 422 },
      ),
    );

    await expect(request("/api/settings")).rejects.toThrow(
      "field required, value is not valid",
    );
  });

  it("reports an unreachable server rather than leaking a TypeError", async () => {
    globalThis.fetch.mockRejectedValue(new TypeError("Failed to fetch"));

    const error = await request("/api/tracks").catch((thrown) => thrown);

    expect(error).toBeInstanceOf(ApiError);
    expect(error.status).toBe(0);
    expect(error.message).toMatch(/could not reach the server/i);
  });

  it("names the misconfigured proxy when the web app answers an API path", async () => {
    // A reverse proxy that sends /api to the frontend gets the SPA fallback:
    // 200, text/html, index.html. `response.ok` is true, so this used to be
    // handed to callers as data and the app broke later and elsewhere.
    globalThis.fetch.mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers({ "content-type": "text/html; charset=utf-8" }),
      text: async () => "<!doctype html><html><body><div id=root></div></body></html>",
      json: async () => {
        throw new SyntaxError("Unexpected token <");
      },
    });

    const error = await request("/api/tracks").catch((thrown) => thrown);

    expect(error).toBeInstanceOf(ApiError);
    expect(error.message).toMatch(/web app instead of API data/i);
    expect(error.message).toMatch(/reverse proxy/i);
  });

  it("still allows a non-JSON, non-HTML body through", async () => {
    // Artwork and audio are binary; only HTML means "this is the SPA".
    globalThis.fetch.mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers({ "content-type": "text/plain" }),
      text: async () => "ok",
      json: async () => "ok",
    });

    await expect(request("/api/health")).resolves.toBe("ok");
  });

  it("broadcasts a 401 so an expired session returns the user to sign-in", async () => {
    globalThis.fetch.mockResolvedValue(
      jsonResponse({ detail: "Not authenticated" }, { status: 401 }),
    );

    const listener = vi.fn();
    const unsubscribe = onUnauthorized(listener);

    await request("/api/tracks").catch(() => {});

    expect(listener).toHaveBeenCalledTimes(1);
    unsubscribe();
  });

  it("does not broadcast a 401 from the sign-in call, which just means wrong password", async () => {
    globalThis.fetch.mockResolvedValue(
      jsonResponse({ detail: "Invalid username or password" }, { status: 401 }),
    );

    const listener = vi.fn();
    const unsubscribe = onUnauthorized(listener);

    await request("/api/auth/login", {
      method: "POST",
      suppressUnauthorized: true,
    }).catch(() => {});

    expect(listener).not.toHaveBeenCalled();
    unsubscribe();
  });

  it("stops notifying once unsubscribed", async () => {
    globalThis.fetch.mockResolvedValue(jsonResponse({}, { status: 401 }));

    const listener = vi.fn();
    onUnauthorized(listener)();

    await request("/api/tracks").catch(() => {});

    expect(listener).not.toHaveBeenCalled();
  });

  it("rethrows an abort untouched so callers can ignore it", async () => {
    const abortError = new Error("aborted");
    abortError.name = "AbortError";
    globalThis.fetch.mockRejectedValue(abortError);

    await expect(request("/api/tracks")).rejects.toMatchObject({ name: "AbortError" });
  });
});
