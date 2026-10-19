from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI

from gateway.routing.proxy import router as proxy_router


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


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": "gatekeeper",
    }


app.include_router(proxy_router)