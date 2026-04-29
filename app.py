import httpx
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.exceptions import HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.openapi.utils import get_openapi
from slowapi.errors import RateLimitExceeded
from dependencies.database import engine
from dependencies.limiter import limiter
from core.config import settings
from middleware.api_version import APIVersionMiddleware
from middleware.csrf import CSRFMiddleware
from middleware.logging import LoggingMiddleware
from models.base import Base
from routes import auth, profile, test
from utils.custom_content import custom_content


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.limiter = limiter
    app.state.client = httpx.AsyncClient()
    yield
    await app.state.client.aclose()


app = FastAPI(lifespan=lifespan)


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    schema = get_openapi(
        title="Insighta Labs+ API",
        version="1.0.0",
        description="Profile Intelligence Platform",
        routes=app.routes,
    )

    for path, methods in schema.get("paths", {}).items():
        if path.startswith("/api/"):
            for method in methods.values():
                method.setdefault("parameters", []).append(
                    {
                        "name": "X-API-Version",
                        "in": "header",
                        "required": True,
                        "description": "API version — must be 1",
                        "schema": {
                            "type": "string",
                            "default": "1",
                            "enum": ["1"],
                        },
                    }
                )

    app.openapi_schema = schema
    return app.openapi_schema


app.openapi = custom_openapi


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content=custom_content("error", message="Too many requests"),
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    print(f"HTTPException: {str(exc)}")
    return JSONResponse(
        status_code=exc.status_code,
        content=custom_content(
            "error",
            message=exc.detail if isinstance(exc.detail, str) else "Request failed",
        ),
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    print(f"Unhandled exception: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content=custom_content("error", message="Upstream or server failure"),
    )


# Routes
@app.get("/")
def index():
    return {"status": "success", "message": "Welcome to Instalabs API"}


app.include_router(auth.router, prefix="/auth")
app.include_router(profile.router, prefix="/api")
app.include_router(test.router, prefix="/test")


# 3. Runs last — version check (only on /api/* routes)
app.add_middleware(CSRFMiddleware)
app.add_middleware(APIVersionMiddleware)

# 2. Runs second — request logging
app.add_middleware(LoggingMiddleware)

# 1. Runs first — CORS
frontend_origin = settings.FRONTEND_URL.strip().rstrip("/")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        frontend_origin,
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


Base.metadata.create_all(engine)
