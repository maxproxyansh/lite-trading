from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from agent_sdk import LiteAgentClient, LiteAgentError  # noqa: E402


DEFAULT_BASE_URL = "http://127.0.0.1:8000"
DEFAULT_CONFIG_PATH = Path(
    os.environ.get("LITE_AGENT_CONFIG", Path.home() / ".config" / "lite-agent" / "config.json")
).expanduser()


def load_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return {}


def save_config(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2))
    try:
        path.chmod(0o600)
    except OSError:
        pass


def redact_secret(payload: Any, *, show_secret: bool) -> Any:
    if show_secret or not isinstance(payload, dict):
        return payload
    masked = dict(payload)
    if masked.get("api_key"):
        secret = str(masked["api_key"])
        masked["api_key"] = f"{secret[:12]}..." if len(secret) > 12 else "***"
    return masked


def emit(payload: Any, *, pretty: bool) -> None:
    if pretty:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    print(json.dumps(payload, separators=(",", ":")))


def make_client(args: argparse.Namespace) -> tuple[LiteAgentClient, Path, dict[str, Any]]:
    config_path = Path(args.config).expanduser()
    config = load_config(config_path)
    base_url = args.base_url or os.environ.get("LITE_BASE_URL") or config.get("base_url") or DEFAULT_BASE_URL
    api_key = args.api_key or os.environ.get("LITE_AGENT_API_KEY") or config.get("api_key")
    client = LiteAgentClient(base_url=base_url, api_key=api_key)
    return client, config_path, config


def handle_bootstrap(args: argparse.Namespace) -> Any:
    client, config_path, _config = make_client(args)
    data = client.bootstrap(
        email=args.email,
        password=args.password,
        agent_name=args.agent_name,
        portfolio_kind=args.portfolio_kind,
        scopes=args.scopes,
        expires_in_days=args.expires_in_days,
        rotate_existing=not args.no_rotate,
    )
    save_config(
        config_path,
        {
            "base_url": client.base_url,
            "api_key": data["api_key"],
            "agent_name": data["agent"]["name"],
            "portfolio_id": data["portfolio"]["id"],
            "key_prefix": data["agent"]["key_prefix"],
        },
    )
    payload = redact_secret({**data, "stored_config": str(config_path)}, show_secret=args.show_secret)
    return payload


def handle_signup(args: argparse.Namespace) -> Any:
    client, config_path, _config = make_client(args)
    data = client.signup(
        email=args.email,
        display_name=args.display_name,
        password=args.password,
        agent_name=args.agent_name,
        portfolio_kind=args.portfolio_kind,
        scopes=args.scopes,
        expires_in_days=args.expires_in_days,
        rotate_existing=not args.no_rotate,
    )
    save_config(
        config_path,
        {
            "base_url": client.base_url,
            "api_key": data["api_key"],
            "agent_name": data["agent"]["name"],
            "portfolio_id": data["portfolio"]["id"],
            "key_prefix": data["agent"]["key_prefix"],
        },
    )
    payload = redact_secret({**data, "stored_config": str(config_path)}, show_secret=args.show_secret)
    return payload


def handle_clear_auth(args: argparse.Namespace) -> Any:
    config_path = Path(args.config).expanduser()
    if config_path.exists():
        config_path.unlink()
    return {"cleared": True, "config": str(config_path)}


def handle_profile(args: argparse.Namespace) -> Any:
    client, _, _ = make_client(args)
    return client.profile()


def handle_market_snapshot(args: argparse.Namespace) -> Any:
    client, _, _ = make_client(args)
    return client.snapshot()


def handle_market_expiries(args: argparse.Namespace) -> Any:
    client, _, _ = make_client(args)
    return client.expiries()


def handle_market_chain(args: argparse.Namespace) -> Any:
    client, _, _ = make_client(args)
    return client.chain(expiry=args.expiry)


def handle_market_candles(args: argparse.Namespace) -> Any:
    client, _, _ = make_client(args)
    return client.candles(timeframe=args.timeframe)


def handle_market_depth(args: argparse.Namespace) -> Any:
    client, _, _ = make_client(args)
    return client.depth(args.symbol)


def handle_funds(args: argparse.Namespace) -> Any:
    client, _, _ = make_client(args)
    return client.dhan_funds() if args.dhan else client.funds()


def handle_positions(args: argparse.Namespace) -> Any:
    client, _, _ = make_client(args)
    return client.dhan_positions() if args.dhan else client.positions()


def handle_orders_list(args: argparse.Namespace) -> Any:
    client, _, _ = make_client(args)
    return client.dhan_orders() if args.dhan else client.orders()


def handle_orders_get(args: argparse.Namespace) -> Any:
    client, _, _ = make_client(args)
    return client.dhan_order_detail(args.order_id) if args.dhan else client.order_detail(args.order_id)


def handle_orders_place(args: argparse.Namespace) -> Any:
    client, _, _ = make_client(args)
    payload = {
        "transaction_type": args.side,
        "quantity": args.quantity,
        "trading_symbol": args.trading_symbol,
        "security_id": args.security_id,
        "expiry": args.expiry,
        "strike": args.strike,
        "option_type": args.option_type,
        "product_type": args.product_type,
        "order_type": args.order_type,
        "validity": args.validity,
        "price": args.price,
        "trigger_price": args.trigger_price,
        "correlationId": args.correlation_id,
    }
    return client.dhan_order(payload)


def handle_orders_cancel(args: argparse.Namespace) -> Any:
    client, _, _ = make_client(args)
    return client.dhan_cancel_order(args.order_id) if args.dhan else client.cancel_order(args.order_id)


def handle_square_off(args: argparse.Namespace) -> Any:
    client, _, _ = make_client(args)
    if args.all:
        return client.square_off_all()
    return client.square_off(args.position_id)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Lite agent CLI")
    parser.add_argument("--base-url", default=None, help="Lite API base URL")
    parser.add_argument("--api-key", default=None, help="Agent API key")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="CLI credential config path")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output")

    subparsers = parser.add_subparsers(dest="command", required=True)

    bootstrap = subparsers.add_parser("bootstrap", help="Authenticate an existing Lite account and issue an agent API key")
    bootstrap.add_argument("--email", required=True)
    bootstrap.add_argument("--password", required=True)
    bootstrap.add_argument("--agent-name", required=True)
    bootstrap.add_argument("--portfolio-kind", default="agent", choices=("agent", "manual"))
    bootstrap.add_argument("--scope", dest="scopes", action="append", default=None)
    bootstrap.add_argument("--expires-in-days", type=int, default=None)
    bootstrap.add_argument("--no-rotate", action="store_true")
    bootstrap.add_argument("--show-secret", action="store_true")
    bootstrap.set_defaults(handler=handle_bootstrap)

    signup = subparsers.add_parser("signup", help="Create a Lite account and immediately issue an agent API key")
    signup.add_argument("--email", required=True)
    signup.add_argument("--display-name", required=True)
    signup.add_argument("--password", required=True)
    signup.add_argument("--agent-name", required=True)
    signup.add_argument("--portfolio-kind", default="agent", choices=("agent", "manual"))
    signup.add_argument("--scope", dest="scopes", action="append", default=None)
    signup.add_argument("--expires-in-days", type=int, default=None)
    signup.add_argument("--no-rotate", action="store_true")
    signup.add_argument("--show-secret", action="store_true")
    signup.set_defaults(handler=handle_signup)

    profile = subparsers.add_parser("profile", help="Show the current agent profile and bound portfolio")
    profile.set_defaults(handler=handle_profile)

    market = subparsers.add_parser("market", help="Read market data with the current agent API key")
    market_subparsers = market.add_subparsers(dest="market_command", required=True)

    market_snapshot = market_subparsers.add_parser("snapshot", help="Show the latest market snapshot")
    market_snapshot.set_defaults(handler=handle_market_snapshot)

    market_expiries = market_subparsers.add_parser("expiries", help="List available expiries")
    market_expiries.set_defaults(handler=handle_market_expiries)

    market_chain = market_subparsers.add_parser("chain", help="Show the option chain")
    market_chain.add_argument("--expiry", default=None)
    market_chain.set_defaults(handler=handle_market_chain)

    market_candles = market_subparsers.add_parser("candles", help="Show OHLC candle data")
    market_candles.add_argument("--timeframe", default="15m")
    market_candles.set_defaults(handler=handle_market_candles)

    market_depth = market_subparsers.add_parser("depth", help="Show bid/ask depth for a symbol")
    market_depth.add_argument("symbol")
    market_depth.set_defaults(handler=handle_market_depth)

    funds = subparsers.add_parser("funds", help="Show available funds for the bound portfolio")
    funds.add_argument("--dhan", action="store_true", help="Use the Dhan-compatible response shape")
    funds.set_defaults(handler=handle_funds)

    positions = subparsers.add_parser("positions", help="List open positions")
    positions.add_argument("--dhan", action="store_true", help="Use the Dhan-compatible response shape")
    positions.set_defaults(handler=handle_positions)

    orders = subparsers.add_parser("orders", help="List, place, inspect, or cancel orders")
    order_subparsers = orders.add_subparsers(dest="orders_command", required=True)

    orders_list = order_subparsers.add_parser("list", help="List orders")
    orders_list.add_argument("--dhan", action="store_true", help="Use the Dhan-compatible response shape")
    orders_list.set_defaults(handler=handle_orders_list)

    orders_get = order_subparsers.add_parser("get", help="Fetch one order")
    orders_get.add_argument("order_id")
    orders_get.add_argument("--dhan", action="store_true", help="Use the Dhan-compatible response shape")
    orders_get.set_defaults(handler=handle_orders_get)

    orders_place = order_subparsers.add_parser("place", help="Place a Dhan-compatible order")
    orders_place.add_argument("--side", required=True, choices=("BUY", "SELL"))
    orders_place.add_argument("--quantity", required=True, type=int)
    orders_place.add_argument("--trading-symbol", default=None)
    orders_place.add_argument("--security-id", default=None)
    orders_place.add_argument("--expiry", default=None)
    orders_place.add_argument("--strike", type=int, default=None)
    orders_place.add_argument("--option-type", choices=("CE", "PE"), default=None)
    orders_place.add_argument("--product-type", choices=("NRML", "MIS"), default="NRML")
    orders_place.add_argument("--order-type", choices=("MARKET", "LIMIT", "SL", "SL-M"), required=True)
    orders_place.add_argument("--validity", choices=("DAY",), default="DAY")
    orders_place.add_argument("--price", type=float, default=None)
    orders_place.add_argument("--trigger-price", type=float, default=None)
    orders_place.add_argument("--correlation-id", required=True)
    orders_place.set_defaults(handler=handle_orders_place)

    orders_cancel = order_subparsers.add_parser("cancel", help="Cancel an order")
    orders_cancel.add_argument("order_id")
    orders_cancel.add_argument("--dhan", action="store_true", help="Use the Dhan-compatible response shape")
    orders_cancel.set_defaults(handler=handle_orders_cancel)

    square_off = subparsers.add_parser("square-off", help="Square off one position or all positions")
    square_off.add_argument("position_id", nargs="?")
    square_off.add_argument("--all", action="store_true")
    square_off.set_defaults(handler=handle_square_off)

    clear_auth = subparsers.add_parser("clear-auth", help="Remove locally stored CLI credentials")
    clear_auth.set_defaults(handler=handle_clear_auth)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if getattr(args, "command", None) == "square-off" and not args.all and not args.position_id:
        parser.error("square-off requires POSITION_ID or --all")
    try:
        payload = args.handler(args)
    except LiteAgentError as exc:
        error = {"error": str(exc), "status_code": exc.status_code, "payload": exc.payload}
        emit(error, pretty=True)
        return 1
    emit(payload, pretty=args.pretty)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
