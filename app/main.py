from __future__ import annotations

import secrets
from contextlib import asynccontextmanager
from typing import Annotated
from urllib.parse import urlparse

from fastapi import Depends, FastAPI, Header, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.browser import BrowserSession
from app.config import get_settings


settings = get_settings()
browser_session = BrowserSession(settings.cdp_url)


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    await browser_session.disconnect()


app = FastAPI(
    title="Cloud Browser Agent API",
    description="Control an existing remote Chromium browser through its CDP endpoint.",
    version="0.1.0",
    lifespan=lifespan,
)


def require_api_key(
    x_api_key: Annotated[str | None, Header()] = None,
) -> None:
    expected = settings.api_key
    if not x_api_key or not secrets.compare_digest(x_api_key, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid X-API-Key",
        )


Auth = Annotated[None, Depends(require_api_key)]


class NavigateRequest(BaseModel):
    url: str = Field(min_length=8, max_length=2048)
    page_index: int = Field(default=0, ge=0)


class SelectorRequest(BaseModel):
    selector: str = Field(min_length=1, max_length=1000)
    page_index: int = Field(default=0, ge=0)


class FillRequest(SelectorRequest):
    value: str = Field(max_length=10_000)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "cloud-browser-agent"}


@app.get("/api/browser/status", dependencies=[Depends(require_api_key)])
async def browser_status():
    try:
        return await browser_session.status()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"CDP connection failed: {exc}") from exc


@app.get("/api/browser/pages", dependencies=[Depends(require_api_key)])
async def browser_pages():
    try:
        return {"pages": await browser_session.list_pages()}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Unable to list pages: {exc}") from exc


@app.post("/api/browser/navigate", dependencies=[Depends(require_api_key)])
async def navigate(request: NavigateRequest):
    parsed = urlparse(request.url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise HTTPException(status_code=400, detail="Only valid http/https URLs are allowed")
    try:
        return await browser_session.navigate(request.url, request.page_index)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Navigation failed: {exc}") from exc


@app.get("/api/browser/snapshot", dependencies=[Depends(require_api_key)])
async def snapshot(
    page_index: Annotated[int, Query(ge=0)] = 0,
):
    try:
        return await browser_session.snapshot(page_index, settings.max_snapshot_chars)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Snapshot failed: {exc}") from exc


@app.post("/api/browser/click", dependencies=[Depends(require_api_key)])
async def click(request: SelectorRequest):
    try:
        return await browser_session.click(request.selector, request.page_index)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Click failed: {exc}") from exc


@app.post("/api/browser/fill", dependencies=[Depends(require_api_key)])
async def fill(request: FillRequest):
    try:
        return await browser_session.fill(
            request.selector, request.value, request.page_index
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Fill failed: {exc}") from exc
