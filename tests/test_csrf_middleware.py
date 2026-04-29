from fastapi import FastAPI
from fastapi.testclient import TestClient

from middleware.csrf import CSRFMiddleware


def make_app():
    app = FastAPI()
    app.add_middleware(CSRFMiddleware)

    @app.post("/unsafe")
    def unsafe():
        return {"status": "success"}

    return app


def test_cookie_auth_post_requires_csrf_header():
    client = TestClient(make_app())
    client.cookies.set("access_token", "cookie-access")
    client.cookies.set("csrf_token", "csrf-value")

    response = client.post("/unsafe")

    assert response.status_code == 403
    assert response.json() == {"status": "error", "message": "CSRF token required"}


def test_cookie_auth_post_accepts_matching_csrf_header():
    client = TestClient(make_app())
    client.cookies.set("access_token", "cookie-access")
    client.cookies.set("csrf_token", "csrf-value")

    response = client.post(
        "/unsafe",
        headers={"X-CSRF-Token": "csrf-value"},
    )

    assert response.status_code == 200
    assert response.json() == {"status": "success"}


def test_bearer_auth_post_does_not_require_csrf_header():
    client = TestClient(make_app())
    client.cookies.set("access_token", "cookie-access")

    response = client.post(
        "/unsafe",
        headers={"Authorization": "Bearer cli-token"},
    )

    assert response.status_code == 200
    assert response.json() == {"status": "success"}
