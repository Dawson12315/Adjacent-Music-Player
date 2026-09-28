"""Response headers that cost nothing and close a class of browser tricks.

The frontend's nginx already sets these on the UI; the API and the uploaded
artwork it serves did not, and in the recommended reverse-proxy layout the
two are the same origin. Uploads in particular are user-supplied bytes served
under an image type: the browser's own refusal to execute them is the only
thing that stopped a script in an "image", and now it is not.
"""

from starlette.types import ASGIApp, Message, Receive, Scope, Send

_COMMON = [
    (b"x-content-type-options", b"nosniff"),
    (b"referrer-policy", b"strict-origin-when-cross-origin"),
    (b"x-frame-options", b"DENY"),
]

# For anything under /uploads: an image can be displayed, and nothing else.
_UPLOADS = [
    (b"content-security-policy", b"default-src 'none'; sandbox"),
]


class SecurityHeadersMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        extra = list(_COMMON)

        if path.startswith("/uploads") or path.startswith("/legacy-uploads"):
            extra.extend(_UPLOADS)

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                present = {name.lower() for name, _ in headers}
                headers.extend((name, value) for name, value in extra if name not in present)
                message = {**message, "headers": headers}

            await send(message)

        await self.app(scope, receive, send_with_headers)
