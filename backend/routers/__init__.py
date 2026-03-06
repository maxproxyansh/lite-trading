from .analytics import router as analytics
from .agent import router as agent
from .auth import admin_router as admin
from .auth import router as auth
from .funds import router as funds
from .market import router as market
from .orders import router as orders
from .portfolios import router as portfolios
from .positions import router as positions
from .signals import router as signals
from .websocket import router as websocket

__all__ = [
    "admin",
    "agent",
    "analytics",
    "auth",
    "funds",
    "market",
    "orders",
    "portfolios",
    "positions",
    "signals",
    "websocket",
]
