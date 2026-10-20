
import hashlib
import logging

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import selectinload

from contextlib import asynccontextmanager

import httpx
import uuid
import os
import secrets
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


from gateway.routing.proxy import router as proxy_router

from gateway.database.connection import AsyncSessionLocal
from gateway.database.models import ApiClient


logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.http_client = httpx.AsyncClient(
        timeout=httpx.Timeout(3.0, connect=1.0),
        follow_redirects=False,
    )
    try:
        yield
    finally:
        await app.state.http_client.aclose()


app = FastAPI(
    title="GateKeeper API Gateway",
    version="0.1.0",
    lifespan=lifespan,
)



@app.middleware("http")
async def authenticate_and_trace(request: Request, call_next):
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id

    path = request.url.path
    if path == "/api" or path.startswith("/api/"):
        supplied_key = request.headers.get("X-API-Key", "")
        prefix, separator, secret = supplied_key.partition(".")

        if not separator or not prefix or not secret:
            response = JSONResponse(
                status_code=401,
                content={"detail": "Invalid or missing API key"},
            )
            response.headers["X-Request-ID"] = request_id
            return response

        try:
            async with AsyncSessionLocal() as session:
                client = await session.scalar(
                    select(ApiClient)
                    .options(
                        selectinload(ApiClient.owner),
                        selectinload(ApiClient.plan),
                    )
                    .where(ApiClient.key_prefix == prefix)
                )

                # Use the same response for unknown prefixes and
                # incorrect secrets to avoid revealing valid prefixes.
                key_hash = hashlib.sha256(
                    supplied_key.encode("utf-8")
                ).hexdigest()

                if client is None or not secrets.compare_digest(
                    client.key_hash if client else "",
                    key_hash,
                ):
                    response = JSONResponse(
                        status_code=401,
                        content={"detail": "Invalid or missing API key"},
                    )
                    response.headers["X-Request-ID"] = request_id
                    return response

                if (
                    not client.is_active
                    or not client.owner.is_active
                    or not client.plan.is_active
                ):
                    response = JSONResponse(
                        status_code=403,
                        content={"detail": "API client is inactive"},
                    )
                    response.headers["X-Request-ID"] = request_id
                    return response

                request.state.client_id = str(client.id)
                request.state.owner_user_id = str(client.owner_user_id)
                request.state.plan_id = str(client.plan_id)
                request.state.plan_name = client.plan.name
                request.state.requests_per_minute = (
                    client.plan.requests_per_minute
                )
                request.state.monthly_quota = client.plan.monthly_quota

        except SQLAlchemyError:
            logger.exception("Database error during API-key authentication")
            response = JSONResponse(
                status_code=503,
                content={"detail": "Authentication service unavailable"},
            )
            response.headers["X-Request-ID"] = request_id
            return response

    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": "gatekeeper",
    }


app.include_router(proxy_router)