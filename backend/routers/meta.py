from __future__ import annotations

from fastapi import APIRouter, Request

from config import get_settings
from schemas import (
    AgentAuthMeta,
    ApiMetaResponse,
    AuthContractMeta,
    HumanAuthMeta,
    MarketDataContractMeta,
    WebSocketEventMeta,
    WebSocketMeta,
)
from services.agent_service import agent_links, websocket_event_catalog


settings = get_settings()
router = APIRouter(prefix=settings.api_prefix, tags=["meta"])


def _absolute_http_url(request: Request, path: str) -> str:
    return f"{str(request.base_url).rstrip('/')}{path}"


def _absolute_ws_url(request: Request, path: str) -> str:
    scheme = "wss" if request.url.scheme == "https" else "ws"
    return f"{scheme}://{request.url.netloc}{path}"


@router.get("/meta", response_model=ApiMetaResponse)
def api_meta(request: Request):
    ws_path = f"{settings.api_prefix}/ws"
    links = {
        name: _absolute_http_url(request, path)
        for name, path in agent_links().items()
        if name != "websocket"
    }
    links["websocket"] = _absolute_ws_url(request, ws_path)
    return ApiMetaResponse(
        app=settings.app_name,
        version=settings.app_version,
        api_prefix=settings.api_prefix,
        base_url=str(request.base_url).rstrip("/"),
        meta_url=_absolute_http_url(request, f"{settings.api_prefix}/meta"),
        docs_url=_absolute_http_url(request, f"{settings.api_prefix}/docs"),
        openapi_url=_absolute_http_url(request, f"{settings.api_prefix}/openapi.json"),
        redoc_url=_absolute_http_url(request, f"{settings.api_prefix}/redoc"),
        websocket=WebSocketMeta(
            path=ws_path,
            url=_absolute_ws_url(request, ws_path),
            events=[
                WebSocketEventMeta(type=event_type, description=description)
                for event_type, description in websocket_event_catalog()
            ],
        ),
        auth=AuthContractMeta(
            human=HumanAuthMeta(
                login_path=f"{settings.api_prefix}/auth/login",
                refresh_path=f"{settings.api_prefix}/auth/refresh",
                access_token_expires_in_seconds=settings.access_token_minutes * 60,
            ),
            agent=AgentAuthMeta(
                bootstrap_path=f"{settings.api_prefix}/agent/bootstrap",
                signup_path=f"{settings.api_prefix}/agent/signup",
                default_key_expires_in_days=settings.agent_key_default_days,
            ),
        ),
        market_data=MarketDataContractMeta(
            pcr_description="PCR is total put open interest divided by total call open interest across all loaded strikes for the active expiry.",
        ),
        links=links,
    )
