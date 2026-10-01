"""A session that renews itself while it is being used.

The sign-in cookie carries a week's life and used to be minted only at
sign-in, so "stay signed in" ended exactly a week later however much the app
was used in between — and the phone, told only that the session was gone,
cleared the preference with it. Here any request that arrives with a valid
session cookie past half its life goes back out with a fresh one, so a device
in regular use never reaches the expiry. A device left alone for the whole
window still signs in again.

What is deliberately not renewed: an expired cookie (that is a sign-in, not a
renewal), a stream token (it carries "purpose" and travels in URLs), a
response the server refused as unauthenticated or forbidden, and any response
that sets the session cookie itself — sign-in, a password change and sign-out
each decide their own.
"""

from starlette.requests import cookie_parser
from starlette.responses import Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.config import settings
from app.services.auth import (
    decode_access_token,
    reissue_access_token,
    session_token_needs_refresh,
    set_session_cookie,
)


def session_cookie_from_request(headers: list[tuple[bytes, bytes]]) -> str | None:
    """The session cookie's value, read out of the raw Cookie header.

    Starlette's own parser, so that the token renewed here is always the token
    `get_current_user` authenticated with: a request can carry the name twice
    (a cookie set for the host and another for the parent domain), and the two
    must not pick different ones.
    """
    for key, value in headers:
        if key.lower() == b"cookie":
            return cookie_parser(value.decode("latin-1")).get(settings.auth_cookie_name)

    return None


def sets_session_cookie(headers: list[tuple[bytes, bytes]]) -> bool:
    prefix = f"{settings.auth_cookie_name}=".encode("latin-1")

    return any(
        key.lower() == b"set-cookie" and value.startswith(prefix) for key, value in headers
    )


def session_cookie_header(token: str) -> bytes:
    """The Set-Cookie line for a token, with the attributes sign-in uses."""
    carrier = Response()
    set_session_cookie(carrier, token)

    return carrier.headers["set-cookie"].encode("latin-1")


class SessionRefreshMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        token = session_cookie_from_request(scope.get("headers", []))
        payload = decode_access_token(token) if token else None

        if not session_token_needs_refresh(payload):
            await self.app(scope, receive, send)
            return

        # Minted once, before the response: the claims are the ones this
        # request authenticated with.
        refreshed = session_cookie_header(reissue_access_token(payload))

        async def send_with_refreshed_cookie(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = message.get("headers", [])

                # 401 and 403 are the server declining this session; renewing
                # the cookie on the way out would contradict the answer.
                if message["status"] not in (401, 403) and not sets_session_cookie(headers):
                    message = {**message, "headers": [*headers, (b"set-cookie", refreshed)]}

            await send(message)

        await self.app(scope, receive, send_with_refreshed_cookie)
