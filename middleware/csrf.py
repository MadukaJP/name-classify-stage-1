import secrets

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from utils.custom_content import custom_content


UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


class CSRFMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        auth_header = request.headers.get("Authorization", "")
        uses_cookie_auth = (
            not auth_header.startswith("Bearer ")
            and (
                "access_token" in request.cookies
                or "refresh_token" in request.cookies
            )
        )

        if request.method in UNSAFE_METHODS and uses_cookie_auth:
            csrf_cookie = request.cookies.get("csrf_token")
            csrf_header = request.headers.get("X-CSRF-Token")

            if not csrf_cookie or not csrf_header:
                return JSONResponse(
                    status_code=403,
                    content=custom_content("error", message="CSRF token required"),
                )

            if not secrets.compare_digest(csrf_cookie, csrf_header):
                return JSONResponse(
                    status_code=403,
                    content=custom_content("error", message="Invalid CSRF token"),
                )

        return await call_next(request)
