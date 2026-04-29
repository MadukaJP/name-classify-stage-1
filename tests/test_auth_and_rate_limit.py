from uuid import uuid4

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from dependencies.auth import require_admin
from dependencies.limiter import rate_limit_key
from routes.auth import CLIAuthPayload
from utils.tokens import create_access_token


class DummyUser:
    def __init__(self, role: str):
        self.role = role


def make_request(headers=None, cookies=None):
    cookie_header = ""
    if cookies:
        cookie_header = "; ".join(f"{key}={value}" for key, value in cookies.items())

    raw_headers = []
    for key, value in (headers or {}).items():
        raw_headers.append((key.lower().encode(), value.encode()))
    if cookie_header:
        raw_headers.append((b"cookie", cookie_header.encode()))

    return Request({
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": raw_headers,
        "client": ("127.0.0.1", 12345),
    })


def test_rate_limit_key_prefers_authenticated_user():
    user_id = uuid4()
    token = create_access_token(user_id)
    request = make_request(headers={"Authorization": f"Bearer {token}"})

    assert rate_limit_key(request) == f"user:{user_id}"


def test_rate_limit_key_falls_back_to_ip_for_unauthenticated_request():
    request = make_request()

    assert rate_limit_key(request) == "ip:127.0.0.1"


def test_cli_oauth_payload_only_allows_local_redirects():
    payload = CLIAuthPayload(
        code="oauth-code",
        code_verifier="pkce-secret",
        redirect_uri="http://127.0.0.1:52391/callback",
    )

    assert payload.redirect_uri == "http://127.0.0.1:52391/callback"

    with pytest.raises(ValueError):
        CLIAuthPayload(
            code="oauth-code",
            code_verifier="pkce-secret",
            redirect_uri="https://example.com/callback",
        )


def test_require_admin_rejects_analyst():
    with pytest.raises(HTTPException) as exc:
        require_admin(DummyUser("analyst"))

    assert exc.value.status_code == 403
    assert exc.value.detail == "Admin access required"
