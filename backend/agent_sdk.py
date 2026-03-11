from __future__ import annotations

from typing import Any
from urllib.parse import quote

import httpx


class LiteAgentError(RuntimeError):
    def __init__(self, message: str, *, status_code: int = 0, payload: Any | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload


class LiteAgentClient:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str | None = None,
        timeout: float = 15.0,
        user_agent: str = "lite-agent-sdk/1.0",
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.user_agent = user_agent

    def set_api_key(self, api_key: str | None) -> None:
        self.api_key = api_key

    def bootstrap(
        self,
        *,
        email: str,
        password: str,
        agent_name: str,
        portfolio_kind: str = "agent",
        scopes: list[str] | None = None,
        expires_in_days: int | None = None,
        rotate_existing: bool = True,
    ) -> dict[str, Any]:
        payload = {
            "email": email,
            "password": password,
            "agent_name": agent_name,
            "portfolio_kind": portfolio_kind,
            "scopes": scopes or [],
            "expires_in_days": expires_in_days,
            "rotate_existing": rotate_existing,
        }
        data = self._request("POST", "/api/v1/agent/bootstrap", json_data=payload, require_api_key=False)
        self.api_key = data.get("api_key")
        return data

    def signup(
        self,
        *,
        email: str,
        display_name: str,
        password: str,
        agent_name: str,
        portfolio_kind: str = "agent",
        scopes: list[str] | None = None,
        expires_in_days: int | None = None,
        rotate_existing: bool = True,
    ) -> dict[str, Any]:
        payload = {
            "email": email,
            "display_name": display_name,
            "password": password,
            "agent_name": agent_name,
            "portfolio_kind": portfolio_kind,
            "scopes": scopes or [],
            "expires_in_days": expires_in_days,
            "rotate_existing": rotate_existing,
        }
        data = self._request("POST", "/api/v1/agent/signup", json_data=payload, require_api_key=False)
        self.api_key = data.get("api_key")
        return data

    def profile(self) -> dict[str, Any]:
        return self._request("GET", "/api/v1/agent/me")

    def snapshot(self) -> dict[str, Any]:
        return self._request("GET", "/api/v1/market/snapshot")

    def expiries(self) -> dict[str, Any]:
        return self._request("GET", "/api/v1/market/expiries")

    def chain(self, expiry: str | None = None) -> dict[str, Any]:
        params = {"expiry": expiry} if expiry else None
        return self._request("GET", "/api/v1/market/chain", params=params)

    def candles(
        self,
        timeframe: str = "15m",
        before: int | None = None,
        symbol: str | None = None,
        security_id: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"timeframe": timeframe}
        if before is not None:
            params["before"] = before
        if symbol:
            params["symbol"] = symbol
        if security_id:
            params["security_id"] = security_id
        return self._request("GET", "/api/v1/market/candles", params=params)

    def depth(self, symbol: str) -> dict[str, Any]:
        return self._request("GET", f"/api/v1/market/depth/{quote(symbol, safe='')}")

    def funds(self) -> dict[str, Any]:
        return self._request("GET", "/api/v1/agent/funds")

    def alerts(self) -> list[dict[str, Any]]:
        return self._request("GET", "/api/v1/agent/alerts")

    def create_alert(
        self,
        symbol: str,
        target_price: float,
        direction: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"symbol": symbol, "target_price": target_price}
        if direction is not None:
            payload["direction"] = direction
        return self._request("POST", "/api/v1/agent/alerts", json_data=payload)

    def delete_alert(self, alert_id: str) -> None:
        return self._request("DELETE", f"/api/v1/agent/alerts/{alert_id}")

    def positions(self) -> list[dict[str, Any]]:
        return self._request("GET", "/api/v1/agent/positions")

    def orders(
        self,
        *,
        status: str | None = None,
        symbol: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        offset: int = 0,
        limit: int = 50,
        sort: str = "desc",
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"offset": offset, "limit": limit, "sort": sort}
        if status:
            params["status"] = status
        if symbol:
            params["symbol"] = symbol
        if date_from:
            params["from"] = date_from
        if date_to:
            params["to"] = date_to
        return self._request("GET", "/api/v1/agent/orders", params=params)

    def order(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/api/v1/agent/orders", json_data=payload)

    def order_detail(self, order_id: str) -> dict[str, Any]:
        return self._request("GET", f"/api/v1/agent/orders/{order_id}")

    def cancel_order(self, order_id: str) -> dict[str, Any]:
        return self._request("POST", f"/api/v1/agent/orders/{order_id}/cancel")

    def modify_order(
        self,
        order_id: str,
        *,
        price: float | None = None,
        trigger_price: float | None = None,
        quantity: int | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        if price is not None:
            payload["price"] = price
        if trigger_price is not None:
            payload["trigger_price"] = trigger_price
        if quantity is not None:
            payload["quantity"] = quantity
        return self._request("PATCH", f"/api/v1/agent/orders/{order_id}", json_data=payload)

    def close_position(self, position_id: str, quantity: int | None = None) -> dict[str, Any]:
        params = {"quantity": quantity} if quantity is not None else None
        return self._request("POST", f"/api/v1/agent/positions/{position_id}/close", params=params)

    def square_off(self, position_id: str, quantity: int | None = None) -> dict[str, Any]:
        params = {"quantity": quantity} if quantity is not None else None
        return self._request("POST", f"/api/v1/agent/positions/{position_id}/square-off", params=params)

    def square_off_all(self) -> list[dict[str, Any]]:
        return self._request("POST", "/api/v1/agent/positions/square-off")

    def webhooks(self) -> list[dict[str, Any]]:
        return self._request("GET", "/api/v1/agent/webhooks")

    def create_webhook(self, url: str, events: list[str]) -> dict[str, Any]:
        return self._request("POST", "/api/v1/agent/webhooks", json_data={"url": url, "events": events})

    def delete_webhook(self, webhook_id: str) -> None:
        return self._request("DELETE", f"/api/v1/agent/webhooks/{webhook_id}")

    def dhan_funds(self) -> dict[str, Any]:
        return self._request("GET", "/api/v1/agent/dhan/fundlimit")

    def dhan_positions(self) -> list[dict[str, Any]]:
        return self._request("GET", "/api/v1/agent/dhan/positions")

    def dhan_orders(self) -> list[dict[str, Any]]:
        return self._request("GET", "/api/v1/agent/dhan/orders")

    def dhan_order(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/api/v1/agent/dhan/orders", json_data=payload)

    def dhan_order_detail(self, order_id: str) -> dict[str, Any]:
        return self._request("GET", f"/api/v1/agent/dhan/orders/{order_id}")

    def dhan_cancel_order(self, order_id: str) -> dict[str, Any]:
        return self._request("DELETE", f"/api/v1/agent/dhan/orders/{order_id}")

    def _request(
        self,
        method: str,
        path: str,
        *,
        json_data: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        require_api_key: bool = True,
    ) -> Any:
        headers = {"Accept": "application/json", "User-Agent": self.user_agent}
        if require_api_key:
            if not self.api_key:
                raise LiteAgentError("Missing API key")
            headers["X-API-Key"] = self.api_key
        try:
            response = httpx.request(
                method,
                f"{self.base_url}{path}",
                json=json_data,
                params=params,
                headers=headers,
                timeout=self.timeout,
            )
        except httpx.HTTPError as exc:
            raise LiteAgentError(str(exc)) from exc
        if response.status_code >= 400:
            payload: Any
            try:
                payload = response.json()
            except ValueError:
                payload = response.text
            detail = payload.get("detail") if isinstance(payload, dict) else payload
            raise LiteAgentError(str(detail), status_code=response.status_code, payload=payload)
        if response.status_code == 204:
            return None
        return response.json()
