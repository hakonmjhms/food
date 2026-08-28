"""Anonymous voter identity, CSRF and rate-limiting helpers.

There is no admin and no login of any kind. Every visitor is just an anonymous
browser identified by an opaque cookie (`voter_id`), used only to stop the same
browser from voting twice in a week - for both the cake prediction and the "what
was the actual cake" report - and to show "your" pick/streak. It is never
displayed or exposed to anyone else.
"""

import secrets
import time
from collections import defaultdict

from fastapi import HTTPException, Request, Response, status

from .config import get_settings

VOTER_COOKIE_NAME = "voter_id"
VOTER_COOKIE_MAX_AGE = 60 * 60 * 24 * 365 * 2  # ~2 years, so votes stick without a login
SESSION_CSRF_KEY = "csrf_token"


def get_voter_token(request: Request) -> str:
    """Return this browser's anonymous voter id, generating one if it doesn't have one yet.

    The caller must attach it to the outgoing response via `attach_voter_cookie` so
    it's persisted for next time.
    """
    return request.cookies.get(VOTER_COOKIE_NAME) or secrets.token_urlsafe(24)


def attach_voter_cookie(response: Response, token: str) -> Response:
    settings = get_settings()
    response.set_cookie(
        key=VOTER_COOKIE_NAME,
        value=token,
        max_age=VOTER_COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=settings.app_base_url.startswith("https://"),
    )
    return response


def get_or_create_csrf_token(request: Request) -> str:
    token = request.session.get(SESSION_CSRF_KEY)
    if not token:
        token = secrets.token_urlsafe(32)
        request.session[SESSION_CSRF_KEY] = token
    return token


def verify_csrf_token(request: Request, submitted_token: str | None) -> None:
    expected = request.session.get(SESSION_CSRF_KEY)
    if not expected or not submitted_token or not secrets.compare_digest(expected, submitted_token):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Ógilt eða vantar CSRF-tóka")


class RateLimiter:
    """Simple in-memory sliding-window rate limiter, keyed by an arbitrary string (e.g. user id)."""

    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._hits: dict[str, list[float]] = defaultdict(list)

    def check(self, key: str) -> None:
        now = time.monotonic()
        window_start = now - self.window_seconds
        hits = [t for t in self._hits[key] if t > window_start]
        hits.append(now)
        self._hits[key] = hits
        if len(hits) > self.max_requests:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Of margar beiðnir - vinsamlegast hægðu á þér",
            )


vote_rate_limiter = RateLimiter(max_requests=10, window_seconds=60)
actual_vote_rate_limiter = RateLimiter(max_requests=10, window_seconds=60)
