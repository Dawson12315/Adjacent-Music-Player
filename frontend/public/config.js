// Runtime configuration hook.
//
// index.html loads this as a classic script before the app bundle, so it must not use
// ES module syntax. In production `frontend/Dockerfile` overwrites this file at
// container start with the real API_BASE_URL from the environment; in development the
// empty value below leaves src/config.js to fall back to the current host on port 8000.
window.APP_CONFIG = window.APP_CONFIG || { API_BASE_URL: "" };
