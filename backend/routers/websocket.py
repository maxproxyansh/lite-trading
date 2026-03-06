from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from config import get_settings
from database import SessionLocal
from models import AgentApiKey, User
from security import decode_access_token, hash_secret


settings = get_settings()
router = APIRouter(tags=["ws"])
connected_clients: set[WebSocket] = set()


async def broadcast_message(event_type: str, payload: dict[str, Any]) -> None:
    dead: set[WebSocket] = set()
    message = json.dumps({"type": event_type, "payload": payload}, default=str)
    for client in connected_clients:
        try:
            await client.send_text(message)
        except Exception:  # noqa: BLE001
            dead.add(client)
    connected_clients.difference_update(dead)


@router.websocket(f"{settings.api_prefix}/ws")
async def websocket_endpoint(websocket: WebSocket):
    db: Session = SessionLocal()
    try:
        token = websocket.query_params.get("token")
        api_key = websocket.query_params.get("api_key")
        authorized = False
        if token:
            try:
                payload = decode_access_token(token)
                user = db.query(User).filter(User.id == payload.get("sub"), User.is_active.is_(True)).first()
                authorized = user is not None
            except Exception:  # noqa: BLE001
                authorized = False
        elif api_key:
            key = db.query(AgentApiKey).filter(
                AgentApiKey.key_hash == hash_secret(api_key),
                AgentApiKey.is_active.is_(True),
            ).first()
            authorized = key is not None

        if not authorized:
            await websocket.close(code=4401)
            return
    finally:
        db.close()

    await websocket.accept()
    connected_clients.add(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        connected_clients.discard(websocket)
    finally:
        connected_clients.discard(websocket)
