"""Reject oversized request bodies before anything reads them.

FastAPI buffers the entire body before dependency resolution, so
authentication runs *after* a multi-gigabyte JSON payload has already been
accumulated in memory. That makes every pre-auth endpoint (login, setup-admin,
password recovery) a memory-exhaustion lever for an anonymous client, and the
artwork uploads a disk/IO lever.

This is pure ASGI middleware rather than a BaseHTTPMiddleware subclass so it
runs before the request body is consumed, and so it cannot interfere with the
streaming responses the app serves (audio, HLS) — it only ever inspects
request headers and, for chunked uploads, counts bytes as they arrive.

A reverse proxy should ALSO cap body size (see the README's internet-exposure
section); this is the backstop for direct/LAN access where no proxy exists.
"""

import logging

from starlette.datastructures import Headers
from starlette.types import ASGIApp, Receive, Scope, Send

logger = logging.getLogger(__name__)

# Anything that is not an upload is JSON, and the largest legitimate JSON body
# the app sends is a playlist reorder — kilobytes. A megabyte is generous.
DEFAULT_MAX_BODY_BYTES = 1 * 1024 * 1024

# Artwork uploads: the frontend sends original-resolution images, so this needs
# real headroom while still bounding the damage.
UPLOAD_MAX_BODY_BYTES = 20 * 1024 * 1024

# Endpoints whose bodies are file uploads rather than JSON.
UPLOAD_PATH_MARKERS = ("/artwork",)


def _limit_for(path: str) -> int:
    if any(marker in path for marker in UPLOAD_PATH_MARKERS):
        return UPLOAD_MAX_BODY_BYTES
    return DEFAULT_MAX_BODY_BYTES


class BodySizeLimitMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope.get("method") in ("GET", "HEAD", "OPTIONS"):
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        max_bytes = _limit_for(path)

        headers = Headers(scope=scope)
        content_length = headers.get("content-length")

        if content_length is not None:
            try:
                declared = int(content_length)
            except ValueError:
                declared = None

            if declared is not None and declared > max_bytes:
                logger.warning(
                    "Rejected %s %s: declared body %s bytes exceeds %s",
                    scope.get("method"),
                    path,
                    declared,
                    max_bytes,
                )
                await _send_413(send, max_bytes)
                return

        # Chunked uploads declare no length, so count as the body streams in and
        # cut it off the moment it crosses the limit.
        received = 0
        exceeded = False

        async def counting_receive():
            nonlocal received, exceeded

            message = await receive()

            if message["type"] == "http.request":
                received += len(message.get("body", b""))

                if received > max_bytes:
                    exceeded = True
                    logger.warning(
                        "Rejected %s %s: streamed body exceeded %s bytes",
                        scope.get("method"),
                        path,
                        max_bytes,
                    )
                    # Ending the stream keeps the app from waiting on a body
                    # that will never legitimately finish.
                    return {"type": "http.disconnect"}

            return message

        await self.app(scope, counting_receive, send)


async def _send_413(send: Send, max_bytes: int) -> None:
    body = (
        b'{"detail":"Request body too large (limit '
        + str(max_bytes).encode()
        + b' bytes)."}'
    )

    await send(
        {
            "type": "http.response.start",
            "status": 413,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode()),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})
