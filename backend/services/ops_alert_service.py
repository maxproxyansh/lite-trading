from __future__ import annotations

import logging

import httpx

from config import get_settings


settings = get_settings()
logger = logging.getLogger("lite.ops-alerts")


async def send_p0_slack_alert(*, title: str, lines: list[str]) -> bool:
    webhook_url = settings.dhan_p0_slack_webhook_url
    if not webhook_url:
        return False

    payload = {"text": "\n".join([title, *[line for line in lines if line]])}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(webhook_url, json=payload)
            response.raise_for_status()
        return True
    except Exception:  # noqa: BLE001
        logger.exception("Failed to deliver Slack P0 alert")
        return False
