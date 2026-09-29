"""Weak ETags on the index routes, so an unchanged index costs one round trip.

The phone fetches the artist and album indexes, the genre list and the
playlists on every sign-in and every pull to refresh; on most of those
nothing has changed, and the bytes went over the wire anyway. The body of a
matching GET is hashed here, the hash goes out as a weak ETag, and a request
carrying it back in If-None-Match gets a 304 and no body.

The hash is of the body, not of a version column: an edit that keeps the row
count (a retitled track, a renamed artist) still changes the answer. It saves
the transfer, not the query. Only JSON 200s under the listed prefixes are
touched; streams and everything else pass straight through.
"""

import hashlib

from starlette.types import ASGIApp, Message, Receive, Scope, Send

ETAG_PATH_PREFIXES = (
    "/api/mobile/artists",
    "/api/mobile/albums",
    "/api/artists",
    "/api/albums",
    "/api/genres",
    "/api/playlists",
    "/api/tracks",
)


def etag_for(body: bytes) -> str:
    return 'W/"' + hashlib.sha256(body).hexdigest()[:32] + '"'


def _header(headers, name: bytes) -> bytes | None:
    for key, value in headers:
        if key.lower() == name:
            return value
    return None


def etag_matches(if_none_match: str | None, etag: str) -> bool:
    if not if_none_match:
        return False
    if if_none_match.strip() == "*":
        return True
    wanted = etag[2:] if etag.startswith("W/") else etag
    for candidate in if_none_match.split(","):
        candidate = candidate.strip()
        if candidate.startswith("W/"):
            candidate = candidate[2:]
        if candidate == wanted:
            return True
    return False


class ETagMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if (
            scope["type"] != "http"
            or scope.get("method") != "GET"
            or not scope.get("path", "").startswith(ETAG_PATH_PREFIXES)
        ):
            await self.app(scope, receive, send)
            return

        if_none_match = _header(scope.get("headers", []), b"if-none-match")
        if_none_match = if_none_match.decode("latin-1") if if_none_match else None

        start_message: Message | None = None
        chunks: list[bytes] = []
        passthrough = False

        async def send_buffered(message: Message) -> None:
            nonlocal start_message, passthrough

            if passthrough:
                await send(message)
                return

            if message["type"] == "http.response.start":
                content_type = _header(message.get("headers", []), b"content-type") or b""
                if message["status"] != 200 or not content_type.startswith(b"application/json"):
                    passthrough = True
                    await send(message)
                    return
                start_message = message
                return

            if message["type"] != "http.response.body":
                await send(message)
                return

            chunks.append(message.get("body", b""))
            if message.get("more_body"):
                return

            body = b"".join(chunks)
            etag = etag_for(body)
            headers = [
                (key, value)
                for key, value in start_message.get("headers", [])
                if key.lower() not in (b"etag", b"cache-control")
            ]
            headers.append((b"cache-control", b"private, no-cache"))
            headers.append((b"etag", etag.encode("latin-1")))

            if etag_matches(if_none_match, etag):
                await send(
                    {
                        "type": "http.response.start",
                        "status": 304,
                        "headers": [
                            (key, value)
                            for key, value in headers
                            if key.lower() not in (b"content-length", b"content-type")
                        ],
                    }
                )
                await send({"type": "http.response.body", "body": b""})
                return

            await send({**start_message, "headers": headers})
            await send({"type": "http.response.body", "body": body})

        await self.app(scope, receive, send_buffered)
