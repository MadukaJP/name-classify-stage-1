from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from fastapi.responses import JSONResponse
import httpx
from database import engine
from models.base import Base
from routes import profile
from utils.custom_content import custom_content



# Lifespan
@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.client = httpx.AsyncClient()
    yield
    await app.state.client.aclose()


app = FastAPI(lifespan=lifespan)

app.include_router(profile.router)

# CORS
origins = ['*']

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    print(f"Exception String: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content=custom_content(
            "error",
            message="Upstream or server failure"
        ),
    )



Base.metadata.create_all(engine)
