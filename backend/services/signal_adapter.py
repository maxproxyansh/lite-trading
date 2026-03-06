from __future__ import annotations

import asyncio
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from config import get_settings
from database import SessionLocal
from models import Signal
from services.audit import log_audit


settings = get_settings()


def _parse_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            return datetime.now(timezone.utc)
    return datetime.now(timezone.utc)


def _as_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalize_confidence_label(raw: Any, score: float) -> str:
    if isinstance(raw, str) and raw.strip():
        return raw.strip().upper()
    if score >= 75:
        return "HIGH"
    if score >= 55:
        return "MEDIUM"
    return "LOW"


def normalize_signal_payload(data: dict[str, Any]) -> dict[str, Any]:
    score = _as_float(data.get("confidence_score"))
    if score is None:
        numeric_conf = _as_float(data.get("confidence"))
        score = numeric_conf if numeric_conf is not None else 0.0

    option_type = (data.get("option_type") or data.get("instrument") or "").upper() or None
    trade_text = data.get("trade")
    if not option_type and isinstance(trade_text, str):
        parts = trade_text.upper().split()
        if parts and parts[-1] in {"CE", "PE"}:
            option_type = parts[-1]

    strike = data.get("strike")
    try:
        strike = int(strike) if strike is not None else None
    except (TypeError, ValueError):
        strike = None

    entry_low = _as_float(data.get("entry_low"))
    entry_high = _as_float(data.get("entry_high"))
    if entry_low is None and isinstance(data.get("entry_range"), list) and data["entry_range"]:
        entry_low = _as_float(data["entry_range"][0])
    if entry_high is None and isinstance(data.get("entry_range"), list) and len(data["entry_range"]) > 1:
        entry_high = _as_float(data["entry_range"][1])

    target_price = _as_float(data.get("target"))
    stop_loss = _as_float(data.get("stop_loss"))

    target_valid = bool(target_price and entry_high and target_price > entry_high)
    stop_valid = bool(stop_loss and entry_low and 0 < stop_loss < entry_low)
    actionable = bool(
        trade_text
        and option_type in {"CE", "PE"}
        and strike
        and data.get("expiry")
        and score >= settings.signal_min_confidence
    )

    timestamp = data.get("timestamp") or data.get("generated_at")
    generated_at = _parse_datetime(timestamp)
    signal_id = hashlib.sha1(
        json.dumps(
            {
                "timestamp": generated_at.isoformat(),
                "trade": trade_text,
                "strike": strike,
                "option_type": option_type,
                "expiry": data.get("expiry"),
            },
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()

    return {
        "id": signal_id,
        "source": "auto_trader",
        "direction": str(data.get("direction") or "NEUTRAL").upper(),
        "confidence_label": _normalize_confidence_label(data.get("confidence"), score),
        "confidence_score": score,
        "trade_text": trade_text,
        "strike": strike,
        "option_type": option_type,
        "expiry": data.get("expiry"),
        "entry_low": entry_low,
        "entry_high": entry_high,
        "target_price": target_price if target_valid else None,
        "stop_loss": stop_loss if stop_valid else None,
        "index_target": _as_float(data.get("index_target")),
        "index_stop": _as_float(data.get("index_stop")),
        "is_actionable": actionable,
        "target_valid": target_valid,
        "stop_valid": stop_valid,
        "raw_payload": data,
        "generated_at": generated_at,
    }


class SignalAdapter:
    def __init__(self) -> None:
        self.signal_root = settings.signal_root_path
        self.latest_json = self.signal_root / "latest_signal.json"
        self.log_file = self.signal_root / "logs" / "signals.log"
        self._task: asyncio.Task | None = None
        self._broadcast = None

    def set_broadcast(self, broadcast) -> None:
        self._broadcast = broadcast

    async def start(self) -> None:
        if self._task:
            return
        self._task = asyncio.create_task(self._poll_loop())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _poll_loop(self) -> None:
        while True:
            try:
                await self.ingest_once()
            except Exception:  # noqa: BLE001
                pass
            await asyncio.sleep(settings.signal_poll_seconds)

    async def ingest_once(self) -> None:
        db = SessionLocal()
        try:
            updated = False
            latest = self._read_latest_json()
            if latest:
                updated = self._upsert_signal(db, latest) or updated
            for entry in self._read_signal_log_tail():
                updated = self._upsert_signal(db, entry) or updated
            if updated and self._broadcast:
                latest_signal = db.query(Signal).order_by(Signal.generated_at.desc()).first()
                if latest_signal:
                    await self._broadcast(
                        "signal.updated",
                        {
                            "id": latest_signal.id,
                            "direction": latest_signal.direction,
                            "confidence_label": latest_signal.confidence_label,
                            "confidence_score": latest_signal.confidence_score,
                            "trade_text": latest_signal.trade_text,
                            "strike": latest_signal.strike,
                            "option_type": latest_signal.option_type,
                            "expiry": latest_signal.expiry,
                            "generated_at": latest_signal.generated_at.isoformat(),
                            "is_actionable": latest_signal.is_actionable,
                        },
                    )
        finally:
            db.close()

    def _read_latest_json(self) -> dict[str, Any] | None:
        if not self.latest_json.exists():
            return None
        try:
            return json.loads(self.latest_json.read_text())
        except Exception:  # noqa: BLE001
            return None

    def _read_signal_log_tail(self) -> list[dict[str, Any]]:
        if not self.log_file.exists():
            return []
        try:
            lines = self.log_file.read_text().splitlines()[-50:]
        except Exception:  # noqa: BLE001
            return []
        result = []
        for line in lines:
            try:
                result.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return result

    def _upsert_signal(self, db: Session, payload: dict[str, Any]) -> bool:
        normalized = normalize_signal_payload(payload)
        existing = db.query(Signal).filter(Signal.id == normalized["id"]).first()
        if existing:
            return False
        signal = Signal(**normalized)
        db.add(signal)
        log_audit(
            db,
            actor_type="system",
            actor_id=None,
            action="signal.ingested",
            entity_type="signal",
            entity_id=signal.id,
            details={"direction": signal.direction, "confidence_score": signal.confidence_score},
        )
        db.commit()
        return True


signal_adapter = SignalAdapter()
