from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from dataclasses import dataclass
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import or_
from sqlalchemy.orm import Session

from config import get_settings
from database import SessionLocal
from models import AgentApiKey, Portfolio, User
from security import decode_access_token, hash_secret


settings = get_settings()
router = APIRouter(tags=["ws"])


@dataclass(frozen=True, slots=True)
class WebSocketClient:
    user_id: str
    portfolio_ids: frozenset[str]
    agent_key_id: str | None = None


connected_clients: dict[WebSocket, WebSocketClient] = {}


async def _broadcast_to_clients(clients: list[WebSocket], message: str) -> None:
    if not clients:
        return
    results = await asyncio.gather(
        *(client.send_text(message) for client in clients),
        return_exceptions=True,
    )
    for client, result in zip(clients, results, strict=False):
        if isinstance(result, Exception):
            connected_clients.pop(client, None)


async def broadcast_message(event_type: str, payload: dict[str, Any]) -> None:
    message = json.dumps({"type": event_type, "payload": payload}, default=str, separators=(",", ":"))
    await _broadcast_to_clients(list(connected_clients), message)


async def broadcast_portfolio_message(portfolio_id: str, event_type: str, payload: dict[str, Any]) -> None:
    message = json.dumps({"type": event_type, "payload": payload}, default=str, separators=(",", ":"))
    clients = [
        socket
        for socket, client in connected_clients.items()
        if portfolio_id in client.portfolio_ids
    ]
    await _broadcast_to_clients(clients, message)


async def broadcast_user_message(user_id: str, event_type: str, payload: dict[str, Any]) -> None:
    message = json.dumps({"type": event_type, "payload": payload}, default=str, separators=(",", ":"))
    clients = [
        socket
        for socket, client in connected_clients.items()
        if client.user_id == user_id and client.agent_key_id is None
    ]
    await _broadcast_to_clients(clients, message)


async def broadcast_agent_message(agent_key_id: str, event_type: str, payload: dict[str, Any]) -> None:
    message = json.dumps({"type": event_type, "payload": payload}, default=str, separators=(",", ":"))
    clients = [
        socket
        for socket, client in connected_clients.items()
        if client.agent_key_id == agent_key_id
    ]
    await _broadcast_to_clients(clients, message)


def _bearer_token(value: str | None) -> str | None:
    if not value:
        return None
    scheme, _, token = value.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    return token.strip()


@router.websocket(f"{settings.api_prefix}/ws")
async def websocket_endpoint(websocket: WebSocket):
    db: Session = SessionLocal()
    user_id: str | None = None
    agent_key_id: str | None = None
    try:
        cookie_token = websocket.cookies.get(settings.access_cookie_name)
        bearer_token = _bearer_token(websocket.headers.get("authorization"))
        api_key = websocket.headers.get("x-api-key")
        authorized = False
        portfolio_ids: set[str] = set()
        if cookie_token or bearer_token:
            try:
                payload = decode_access_token(cookie_token or bearer_token or "")
                user = db.query(User).filter(User.id == payload.get("sub"), User.is_active.is_(True)).first()
                authorized = user is not None
                if user:
                    user_id = user.id
                    portfolio_ids = {
                        portfolio_id
                        for (portfolio_id,) in db.query(Portfolio.id).filter(Portfolio.user_id == user.id).all()
                    }
            except Exception:  # noqa: BLE001
                authorized = False
        elif api_key:
            now = datetime.now(timezone.utc)
            key = db.query(AgentApiKey).filter(
                AgentApiKey.key_hash == hash_secret(api_key),
                AgentApiKey.is_active.is_(True),
                AgentApiKey.revoked_at.is_(None),
                or_(AgentApiKey.expires_at.is_(None), AgentApiKey.expires_at > now),
            ).first()
            authorized = bool(key and key.user_id and key.portfolio_id)
            if authorized and key and key.user_id and key.portfolio_id:
                user_id = key.user_id
                portfolio_ids = {key.portfolio_id}
                agent_key_id = key.id

        if not authorized or not user_id:
            await websocket.close(code=4401)
            return
    finally:
        db.close()

    await websocket.accept()
    connected_clients[websocket] = WebSocketClient(
        user_id=user_id,
        portfolio_ids=frozenset(portfolio_ids),
        agent_key_id=agent_key_id,
    )
    try:
        while True:
            message = await websocket.receive_text()
            if message == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        connected_clients.pop(websocket, None)
    finally:
        connected_clients.pop(websocket, None)
