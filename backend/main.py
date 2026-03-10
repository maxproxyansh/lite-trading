from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from config import get_settings
from database import SessionLocal, init_db
from routers import admin, agent, analytics, auth, funds, market, orders, portfolios, positions, signals, websocket
from schemas import HealthResponse
from services.market_data import market_data_service
from services.signal_adapter import signal_adapter
from services.trading_service import process_open_orders_sync
from routers.websocket import broadcast_message


settings = get_settings()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("lite.backend")


async def _process_open_orders() -> None:
    db = SessionLocal()
    try:
        process_open_orders_sync(db)
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    logger.info("Database initialized")

    market_data_service.set_broadcast(broadcast_message)
    market_data_service.set_open_order_processor(_process_open_orders)
    signal_adapter.set_broadcast(broadcast_message)

    await market_data_service.start()
    await signal_adapter.start()
    yield
    await signal_adapter.stop()
    await market_data_service.stop()


app = FastAPI(title=settings.app_name, version="2.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_origin_regex=settings.frontend_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["Authorization", "Content-Type", settings.csrf_header_name, "X-API-Key"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response: Response = await call_next(request)
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    return response

for router in (auth, admin, market, portfolios, orders, positions, funds, analytics, signals, agent, websocket):
    app.include_router(router)


@app.get("/", response_model=HealthResponse)
def root():
    return HealthResponse(status="ok", app=settings.app_name, environment=settings.app_env)


@app.get("/version")
def version():
    return {"version": "2.1.0", "cors_regex": settings.frontend_origin_regex, "origin": settings.frontend_origin}
