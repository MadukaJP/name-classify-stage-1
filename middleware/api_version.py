from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from utils.custom_content import custom_content


class APIVersionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path.startswith("/api/"):
            version = request.headers.get("X-API-Version")
            if version is None:
                return JSONResponse(
                    status_code=400,
                    content=custom_content(
                        "error",
                        message="API version header required",
                    ),
                )
            if version != "1":
                return JSONResponse(
                    status_code=400,
                    content=custom_content(
                        "error",
                        message="Unsupported API version",
                    ),
                )
        return await call_next(request)
