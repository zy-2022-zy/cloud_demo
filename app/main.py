
from __future__ import annotations

import logging
import secrets
from contextlib import asynccontextmanager
from typing import Annotated
from urllib.parse import urlparse

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.browser import BrowserSession
from app.config import get_settings


# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)
logger = logging.getLogger("cloud_browser")

settings = get_settings()
browser_session = BrowserSession(settings.cdp_url)


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info("Cloud Browser API starting")
    yield
    await browser_session.disconnect()
    logger.info("Cloud Browser API stopped")


app = FastAPI(
    title="Cloud Browser Agent API",
    description="Control a remote Chromium browser through CDP.",
    version="0.2.0",
    lifespan=lifespan,
)


# 统一成功响应
def success(data):
    return {
        "success": True,
        "data": data,
        "error": None,
    }


# 统一 API Key 校验
def require_api_key(
    x_api_key: Annotated[str | None, Header()] = None,
) -> None:
    expected = settings.api_key

    if (
        not x_api_key
        or expected == "local-dev-only-change-me"
        or not secrets.compare_digest(x_api_key, expected)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid API key",
        )


# 统一异常响应
@app.exception_handler(HTTPException)
async def http_exception_handler(
    request: Request,
    exc: HTTPException,
):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "data": None,
            "error": {
                "code": "HTTP_ERROR",
                "message": str(exc.detail),
            },
        },
        headers=exc.headers,
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
):
    return JSONResponse(
        status_code=422,
        content={
            "success": False,
            "data": None,
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Request parameters are invalid",
            },
        },
    )


@app.exception_handler(Exception)
async def unexpected_exception_handler(
    request: Request,
    exc: Exception,
):
    logger.exception(
        "Unhandled API error: %s %s",
        request.method,
        request.url.path,
    )

    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "data": None,
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "Internal server error",
            },
        },
    )


Auth = Annotated[None, Depends(require_api_key)]


# 请求参数模型
class NavigateRequest(BaseModel):
    url: str = Field(min_length=8, max_length=2048)
    page_index: int = Field(default=0, ge=0)


class SelectorRequest(BaseModel):
    selector: str = Field(min_length=1, max_length=1000)
    page_index: int = Field(default=0, ge=0)


class FillRequest(SelectorRequest):
    value: str = Field(max_length=10_000)


# 健康检查
@app.get("/health")
async def health():
    return success({"service": "cloud-browser-agent", "status": "ok"})


# 浏览器连接状态
@app.get("/api/browser/status", dependencies=[Depends(require_api_key)])
async def browser_status():
    try:
        return success(await browser_session.status())
    except Exception:
        logger.exception("Failed to get browser status")
        raise HTTPException(
            status_code=502,
            detail="Unable to connect to remote browser",
        )


# 获取浏览器标签页
@app.get("/api/browser/pages", dependencies=[Depends(require_api_key)])
async def browser_pages():
    try:
        return success({"pages": await browser_session.list_pages()})
    except Exception:
        logger.exception("Failed to list browser pages")
        raise HTTPException(
            status_code=502,
            detail="Unable to list browser pages",
        )


# 打开网页
@app.post("/api/browser/navigate", dependencies=[Depends(require_api_key)])
async def navigate(request: NavigateRequest):
    parsed = urlparse(request.url)

    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise HTTPException(
            status_code=400,
            detail="Only valid http/https URLs are allowed",
        )

    try:
        result = await browser_session.navigate(
            request.url,
            request.page_index,
        )
        return success(result)
    except Exception:
        logger.exception("Browser navigation failed")
        raise HTTPException(
            status_code=502,
            detail="Browser navigation failed",
        )


# 读取网页内容
@app.get("/api/browser/snapshot", dependencies=[Depends(require_api_key)])
async def snapshot(
    page_index: Annotated[int, Query(ge=0)] = 0,
):
    try:
        result = await browser_session.snapshot(
            page_index,
            settings.max_snapshot_chars,
        )
        return success(result)
    except Exception:
        logger.exception("Failed to capture browser snapshot")
        raise HTTPException(
            status_code=502,
            detail="Failed to capture browser snapshot",
        )


# 点击网页元素
@app.post("/api/browser/click", dependencies=[Depends(require_api_key)])
async def click(request: SelectorRequest):
    try:
        result = await browser_session.click(
            request.selector,
            request.page_index,
        )
        return success(result)
    except Exception:
        logger.exception("Browser click failed")
        raise HTTPException(
            status_code=502,
            detail="Browser click failed",
        )


# 填写网页输入框
@app.post("/api/browser/fill", dependencies=[Depends(require_api_key)])
async def fill(request: FillRequest):
    try:
        result = await browser_session.fill(
            request.selector,
            request.value,
            request.page_index,
        )
        return success(result)
    except Exception:
        logger.exception("Browser fill failed")
        raise HTTPException(
            status_code=502,
            detail="Browser fill failed",
        )
