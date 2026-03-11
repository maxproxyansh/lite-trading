from __future__ import annotations

from typing import Any

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

    def funds(self) -> dict[str, Any]:
        return self._request("GET", "/api/v1/agent/funds")

    def positions(self) -> list[dict[str, Any]]:
        return self._request("GET", "/api/v1/agent/positions")

    def orders(self) -> list[dict[str, Any]]:
        return self._request("GET", "/api/v1/agent/orders")

    def order(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", "/api/v1/agent/orders", json_data=payload)

    def order_detail(self, order_id: str) -> dict[str, Any]:
        return self._request("GET", f"/api/v1/agent/orders/{order_id}")

    def cancel_order(self, order_id: str) -> dict[str, Any]:
        return self._request("POST", f"/api/v1/agent/orders/{order_id}/cancel")

    def square_off(self, position_id: str) -> dict[str, Any]:
        return self._request("POST", f"/api/v1/agent/positions/{position_id}/square-off")

    def square_off_all(self) -> list[dict[str, Any]]:
        return self._request("POST", "/api/v1/agent/positions/square-off")

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
