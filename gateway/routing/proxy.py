
import logging

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from gateway.database.connection import AsyncSessionLocal
from gateway.database.models import RouteDefinition

logger = logging.getLogger(__name__)

router = APIRouter()

PROXY_METHODS = [
    "GET", "POST", "PUT", "PATCH",
    "DELETE", "OPTIONS", "HEAD",
]

HOP_BY_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
    "host",
    "content-length",
    "content-encoding",
    "x-api-key",
    "x-client-id",
    "x-request-id",
}


def matches_prefix(path: str, prefix: str) -> bool:
    """Match a path on a route boundary, not just a string prefix."""
    prefix = prefix.rstrip("/") or "/"

    if prefix == "/":
        return True

    return path == prefix or path.startswith(prefix + "/")


@router.api_route(
    "/api",
    methods=PROXY_METHODS,
)
@router.api_route(
    "/api/{path:path}",
    methods=PROXY_METHODS,
)
async def proxy_request(request: Request, path: str = ""):
    request_path = request.url.path

    # Load current route configuration from PostgreSQL.
    try:
        async with AsyncSessionLocal() as session:
            result = await session.scalars(
                select(RouteDefinition).where(
                    RouteDefinition.is_active.is_(True)
                )
            )
            routes = list(result.all())

    except SQLAlchemyError:
        logger.exception("Could not load gateway routes")
        return JSONResponse(
            status_code=503,
            content={"detail": "Routing configuration unavailable"},
        )

    # Prefer the most specific matching prefix.
    matching_routes = [
        route
        for route in routes
        if matches_prefix(request_path, route.public_prefix)
    ]

    if not matching_routes:
        return JSONResponse(
            status_code=404,
            content={"detail": "Route not found"},
        )

    route = max(
        matching_routes,
        key=lambda item: len(item.public_prefix.rstrip("/")),
    )

    allowed_methods = {
        method.upper() for method in route.methods
    }

    if request.method not in allowed_methods:
        return JSONResponse(
            status_code=405,
            content={"detail": "Method not allowed for this route"},
            headers={"Allow": ", ".join(sorted(allowed_methods))},
        )

    # Rewrite the public prefix to the upstream prefix.
    public_prefix = route.public_prefix.rstrip("/")
    upstream_prefix = route.upstream_prefix.rstrip("/")

    suffix = request_path[len(public_prefix):]
    upstream_path = upstream_prefix + suffix

    # Build the URL without losing query parameters.
    upstream_url = route.upstream_url.rstrip("/") + upstream_path

    if request.url.query:
        upstream_url += "?" + request.url.query

    # Never trust caller-supplied identity headers.
    headers = {
        key: value
        for key, value in request.headers.items()
        if key.lower() not in HOP_BY_HOP_HEADERS
    }

    headers["X-Client-ID"] = request.state.client_id
    headers["X-Request-ID"] = request.state.request_id

    body = await request.body()

    try:
        upstream_response = await request.app.state.http_client.request(
            method=request.method,
            url=upstream_url,
            headers=headers,
            content=body,
        )

    except httpx.TimeoutException:
        return JSONResponse(
            status_code=504,
            content={"detail": "Upstream request timed out"},
        )

    except httpx.RequestError:
        logger.exception("Upstream request failed")
        return JSONResponse(
            status_code=503,
            content={"detail": "Upstream service unavailable"},
        )

    response_headers = {
        key: value
        for key, value in upstream_response.headers.items()
        if key.lower() not in HOP_BY_HOP_HEADERS
    }

    response_headers["X-Request-ID"] = request.state.request_id

    return Response(
        content=upstream_response.content,
        status_code=upstream_response.status_code,
        headers=response_headers,
    )
