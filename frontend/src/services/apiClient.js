import { API_BASE_URL } from "../config";

/**
 * Error thrown for any non-2xx response. Carries the HTTP status alongside the
 * message so callers can branch on it without re-parsing the response.
 */
export class ApiError extends Error {
  constructor(message, status, detail) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

const unauthorizedListeners = new Set();

/**
 * Subscribe to 401 responses. AuthContext uses this to drop the current user when a
 * session expires, which is the difference between "the app quietly stops working"
 * and "the app returns you to the sign-in screen". Returns an unsubscribe function.
 */
export function onUnauthorized(listener) {
  unauthorizedListeners.add(listener);

  return () => {
    unauthorizedListeners.delete(listener);
  };
}

function notifyUnauthorized() {
  unauthorizedListeners.forEach((listener) => {
    try {
      listener();
    } catch (error) {
      console.error("Unauthorized listener failed", error);
    }
  });
}

function buildUrl(path, params) {
  // The second argument is what lets a same-origin deployment work: with
  // API_BASE_URL empty the first argument is a bare path like "/api/tracks",
  // and `new URL` throws on those unless it is given a base. An absolute
  // API_BASE_URL ignores the base entirely, so this is safe either way.
  const url = new URL(`${API_BASE_URL}${path}`, window.location.origin);

  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null) {
        url.searchParams.set(key, String(value));
      }
    });
  }

  return url.toString();
}

async function parseBody(response) {
  if (response.status === 204) {
    return null;
  }

  const contentType = response.headers.get("content-type") || "";

  if (!contentType.includes("application/json")) {
    return response.text();
  }

  try {
    return await response.json();
  } catch {
    return null;
  }
}

/**
 * FastAPI reports failures as `{"detail": ...}`, where detail is either a string or,
 * for 422s, a list of validation objects. Flatten both into one readable message.
 */
function extractMessage(body, fallback) {
  const detail = body?.detail;

  if (typeof detail === "string") {
    return detail;
  }

  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) => item?.msg)
      .filter(Boolean);

    if (messages.length > 0) {
      return messages.join(", ");
    }
  }

  return fallback;
}

/**
 * Perform an API request.
 *
 * Options:
 *   method   - HTTP verb, defaults to GET
 *   body     - plain object (sent as JSON) or FormData (sent as-is)
 *   params   - query string values; null and undefined entries are dropped
 *   signal   - AbortSignal
 *   noStore  - opt out of HTTP caching, for progress-polling endpoints
 *   suppressUnauthorized - do not broadcast a 401 (used by the sign-in flow, where a
 *                          401 means "wrong password", not "session expired")
 */
export async function request(path, options = {}) {
  const {
    method = "GET",
    body,
    params,
    signal,
    noStore = false,
    suppressUnauthorized = false,
  } = options;

  const isFormData = body instanceof FormData;
  const headers = {};

  if (body !== undefined && !isFormData) {
    headers["Content-Type"] = "application/json";
  }

  if (noStore) {
    headers["Cache-Control"] = "no-cache";
    headers.Pragma = "no-cache";
  }

  let response;

  try {
    response = await fetch(buildUrl(path, params), {
      method,
      credentials: "include",
      signal,
      cache: noStore ? "no-store" : "default",
      headers,
      body: isFormData ? body : body === undefined ? undefined : JSON.stringify(body),
    });
  } catch (error) {
    if (error.name === "AbortError") {
      throw error;
    }

    throw new ApiError(
      "Could not reach the server. Check your connection and try again.",
      0,
      error,
    );
  }

  const parsed = await parseBody(response);

  if (!response.ok) {
    if (response.status === 401 && !suppressUnauthorized) {
      notifyUnauthorized();
    }

    throw new ApiError(
      extractMessage(parsed, `Request failed (${response.status})`),
      response.status,
      parsed?.detail,
    );
  }

  assertNotTheWebAppItself(response, path);

  return parsed;
}

/**
 * Catch the misconfigured-reverse-proxy case, which is otherwise silent.
 *
 * When a proxy sends `/api/...` to the web app's own nginx instead of to the
 * backend, its SPA fallback answers **200 with index.html**. `response.ok` is
 * true, so nothing here objected: the HTML string was handed back to callers
 * as though it were the API's response, and the app failed later and
 * elsewhere — an empty library, a login that neither succeeds nor errors.
 *
 * Only `text/html` counts. The API answers JSON, or binary for artwork and
 * audio; it never answers HTML, so this cannot fire on a legitimate response.
 */
function assertNotTheWebAppItself(response, path) {
  const contentType = response.headers.get("content-type") || "";

  if (!contentType.includes("text/html")) {
    return;
  }

  throw new ApiError(
    `The server returned the web app instead of API data for ${path}. ` +
      "This usually means the reverse proxy is not forwarding /api to the " +
      "backend — check that its /api location proxies to the backend port, " +
      "not to the frontend.",
    0,
    null,
  );
}

export const apiClient = {
  get: (path, options) => request(path, { ...options, method: "GET" }),
  post: (path, body, options) => request(path, { ...options, method: "POST", body }),
  put: (path, body, options) => request(path, { ...options, method: "PUT", body }),
  patch: (path, body, options) => request(path, { ...options, method: "PATCH", body }),
  delete: (path, options) => request(path, { ...options, method: "DELETE" }),
};
