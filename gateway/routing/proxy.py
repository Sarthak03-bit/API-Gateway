from fastapi import APIRouter, Request
from fastapi.responses import Response
import httpx

router = APIRouter(prefix="/api")

UPSTREAMS = {
    "users": "http://user-service:8001",
    "products": "http://product-service:8002",
    "orders": "http://order-service:8003",
}

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
}


@router.api_route(
    "/{service}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
)
@router.api_route(
    "/{service}/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
)
async def proxy_request(
    service: str,
    request: Request,
    path: str = "",
):
    upstream = UPSTREAMS.get(service)

    if upstream is None:
        return Response(
            content='{"detail":"Unknown service"}',
            status_code=404,
            media_type="application/json",
        )

    url = f"{upstream}/{service}"
    if path:
        url += f"/{path}"

    if request.url.query:
        url += f"?{request.url.query}"

    headers = {
        key: value
        for key, value in request.headers.items()
        if key.lower() not in HOP_BY_HOP_HEADERS
    }

    body = await request.body()
    client: httpx.AsyncClient = request.app.state.http_client

    try:
        upstream_response = await client.request(
            method=request.method,
            url=url,
            headers=headers,
            content=body,
        )
    except httpx.TimeoutException:
        return Response(
            content='{"detail":"Upstream service timed out"}',
            status_code=504,
            media_type="application/json",
        )
    except httpx.RequestError:
        return Response(
            content='{"detail":"Upstream service unavailable"}',
            status_code=503,
            media_type="application/json",
        )

    response_headers = {
        key: value
        for key, value in upstream_response.headers.items()
        if key.lower() not in HOP_BY_HOP_HEADERS
    }

    return Response(
        content=upstream_response.content,
        status_code=upstream_response.status_code,
        headers=response_headers,
    )