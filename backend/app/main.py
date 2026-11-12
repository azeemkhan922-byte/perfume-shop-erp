"""Production entry point (FastAPI):  uvicorn app.main:app
All API logic lives in app/api.py; this file only connects it to FastAPI, adds CORS and serves the React build.
NOTE: only syntax-checked in the build environment (FastAPI could not be installed there) - tests/test_api.py covers it."""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool

from app import config
from app.api import dispatch
from app.bootstrap import ensure_owner_from_env
from app.db import connect
from app.schema import create_schema


@asynccontextmanager
async def lifespan(_app):
    if len(config.SECRET_KEY) < 32:
        raise RuntimeError("Set SECRET_KEY (at least 32 characters) before starting.")
    db = connect(config.DATABASE_URL)
    create_schema(db)
    ensure_owner_from_env(db)
    db.conn.close()
    yield


app = FastAPI(title="AZEEM FRAGRANCES ERP", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)

# Needed only if the frontend is hosted on a different address (e.g. during development). Bearer-token auth, no cookies.
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.api_route("/api/{rest:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def api(rest: str, request: Request):
    body = await request.body()
    status, headers, content = await run_in_threadpool(
        dispatch, request.method, "/api/" + rest, dict(request.query_params), body,
        request.headers.get("authorization", ""))
    media_type = headers.pop("Content-Type")
    return Response(content=content, status_code=status, headers=headers, media_type=media_type)


_dist = Path(config.FRONTEND_DIST)
if _dist.is_dir():  # must stay LAST so /api/... is matched first
    app.mount("/", StaticFiles(directory=str(_dist), html=True), name="frontend")
