from __future__ import annotations

import hashlib
import logging
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from config import get_settings
from database import SessionLocal
from models import DhanConsumerState, DhanIncident
from schemas import DhanConsumerStateSummary


logger = logging.getLogger("lite.dhan.incidents")
settings = get_settings()
HEALTHY_STATES = {"healthy", "ok", "connected", "ready"}
SLACK_ALERTABLE_ROOT_CAUSES = {
    "DHAN_AUTH_FAILED",
    "DHAN_PROFILE_FAILED",
    "DHAN_TOKEN_RENEWAL_FAILED",
    "DHAN_TOKEN_REGENERATION_FAILED",
}


@dataclass(frozen=True, slots=True)
class DhanIncidentSnapshot:
    incident_open: bool
    incident_class: str | None
    root_cause: str | None
    message: str | None
    fingerprint: str | None
    opened_at: datetime | None
    affected_consumers: list[str]
    consumer_states: list[DhanConsumerStateSummary]


class DhanIncidentService:
    def __init__(self) -> None:
        self._lock = threading.RLock()

    def reset_runtime_state_for_tests(self) -> None:
        db = SessionLocal()
        try:
            db.query(DhanConsumerState).delete()
            db.query(DhanIncident).delete()
            db.commit()
        finally:
            db.close()

    def snapshot(self) -> DhanIncidentSnapshot:
        db = SessionLocal()
        try:
            record = self._get_or_create_record(db)
            self._prune_consumer_states(db, now=datetime.now(timezone.utc))
            self._reconcile(record, db, alert_sender=None)
            db.commit()
            consumer_states = [
                DhanConsumerStateSummary(
                    consumer=row.consumer,
                    instance_id=row.instance_id,
                    state=row.state,
                    reason=row.reason,
                    message=row.message,
                    observed_at=row.observed_at,
                    generation=row.generation,
                )
                for row in db.query(DhanConsumerState).order_by(DhanConsumerState.consumer, DhanConsumerState.instance_id).all()
            ]
            return DhanIncidentSnapshot(
                incident_open=bool(record.incident_open),
                incident_class=record.incident_class,
                root_cause=record.root_cause,
                message=record.message,
                fingerprint=record.fingerprint,
                opened_at=record.opened_at,
                affected_consumers=list(record.affected_consumers or []),
                consumer_states=consumer_states,
            )
        finally:
            db.close()

    def set_provider_health(
        self,
        *,
        unhealthy: bool,
        reason: str | None,
        message: str | None,
        alert_sender,
    ) -> None:
        with self._lock:
            db = SessionLocal()
            try:
                record = self._get_or_create_record(db)
                record.provider_unhealthy = unhealthy
                record.provider_reason = reason
                record.provider_message = message
                record.provider_updated_at = datetime.now(timezone.utc)
                db.add(record)
                self._reconcile(record, db, alert_sender=alert_sender)
                db.commit()
            finally:
                db.close()

    def mark_consumer_state(
        self,
        *,
        consumer: str,
        instance_id: str,
        state: str,
        reason: str | None,
        message: str | None,
        observed_at: datetime,
        generation: int | None,
        alert_sender,
    ) -> None:
        with self._lock:
            db = SessionLocal()
            try:
                record = self._get_or_create_record(db)
                normalized_state = (state or "").strip().lower()
                row = (
                    db.query(DhanConsumerState)
                    .filter(
                        DhanConsumerState.consumer == consumer,
                        DhanConsumerState.instance_id == instance_id,
                    )
                    .first()
                )
                if normalized_state in HEALTHY_STATES:
                    if row:
                        db.delete(row)
                else:
                    if not row:
                        row = DhanConsumerState(consumer=consumer, instance_id=instance_id)
                    row.state = state
                    row.reason = reason
                    row.message = message
                    row.observed_at = observed_at
                    row.generation = generation
                    db.add(row)
                self._reconcile(record, db, alert_sender=alert_sender)
                db.commit()
            finally:
                db.close()

    def _reconcile(self, record: DhanIncident, db, *, alert_sender, now: datetime | None = None) -> None:
        now = now or datetime.now(timezone.utc)
        self._prune_consumer_states(db, now=now)
        unhealthy_consumers = self._unhealthy_consumers(db)
        affected_consumers = [f"{row.consumer}:{row.instance_id}" for row in unhealthy_consumers]

        desired_class: str | None = None
        desired_root_cause: str | None = None
        desired_message: str | None = None

        if record.provider_unhealthy:
            desired_class = "PROVIDER_UNHEALTHY"
            desired_root_cause = record.provider_reason or "PROVIDER_UNHEALTHY"
            desired_message = record.provider_message or "Dhan provider is unhealthy"
        elif unhealthy_consumers:
            lead = unhealthy_consumers[0]
            desired_class = "CONSUMER_UNHEALTHY"
            desired_root_cause = lead.reason or "CONSUMER_UNHEALTHY"
            desired_message = lead.message or f"{lead.consumer} reported unhealthy Dhan state"

        if desired_class is None:
            if not record.incident_open:
                return
            if alert_sender and self._should_send_slack_alert(record.root_cause):
                try:
                    delivered = alert_sender(
                        state="RECOVERY",
                        incident_class=record.incident_class or "RECOVERY",
                        reason=record.root_cause or "RECOVERY",
                        message="Dhan control plane recovered",
                    )
                except Exception:  # noqa: BLE001
                    logger.exception("Failed to deliver Dhan recovery alert")
                    delivered = False
                if not delivered:
                    record.alert_delivery_error = "recovery-alert-delivery-failed"
            record.incident_open = False
            record.closed_at = now
            record.last_recovery_alert_at = now
            record.incident_class = None
            record.root_cause = None
            record.message = None
            record.fingerprint = None
            record.affected_consumers = []
            record.opened_at = None
            record.last_state_change_at = now
            db.add(record)
            return

        fingerprint = self._fingerprint(
            incident_class=desired_class,
            root_cause=desired_root_cause or "",
            affected_consumers=affected_consumers,
        )
        should_alert = (not record.incident_open) or (record.fingerprint != fingerprint)
        record.incident_open = True
        record.incident_class = desired_class
        record.root_cause = desired_root_cause
        record.message = desired_message
        record.fingerprint = fingerprint
        record.affected_consumers = affected_consumers
        record.last_state_change_at = now
        if should_alert:
            record.opened_at = now
            if alert_sender and self._should_send_slack_alert(desired_root_cause):
                try:
                    delivered = alert_sender(
                        state="P0",
                        incident_class=desired_class,
                        reason=desired_root_cause or desired_class,
                        message=desired_message or desired_class,
                    )
                except Exception:  # noqa: BLE001
                    logger.exception("Failed to deliver Dhan incident alert")
                    delivered = False
                if delivered:
                    record.last_open_alert_at = now
                    record.alert_delivery_error = None
                else:
                    record.alert_delivery_error = "open-alert-delivery-failed"
            elif alert_sender:
                record.alert_delivery_error = None
        db.add(record)

    def _consumer_state_ttl(self) -> timedelta:
        ttl_seconds = max(
            settings.option_chain_refresh_seconds,
            settings.dhan_rest_stale_seconds,
            settings.dhan_realtime_stale_seconds,
        )
        return timedelta(seconds=ttl_seconds)

    def _prune_consumer_states(self, db, *, now: datetime) -> None:
        ttl = self._consumer_state_ttl()
        rows = db.query(DhanConsumerState).all()
        changed = False
        for row in rows:
            state = (row.state or "").strip().lower()
            observed_at = row.observed_at if row.observed_at.tzinfo else row.observed_at.replace(tzinfo=timezone.utc)
            if state in HEALTHY_STATES or now - observed_at > ttl:
                db.delete(row)
                changed = True
        if changed:
            db.flush()

    @staticmethod
    def _fingerprint(*, incident_class: str, root_cause: str, affected_consumers: list[str]) -> str:
        raw = "|".join(["dhan", incident_class, root_cause, ",".join(sorted(affected_consumers))])
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    @staticmethod
    def _should_send_slack_alert(root_cause: str | None) -> bool:
        return (root_cause or "").strip() in SLACK_ALERTABLE_ROOT_CAUSES

    @staticmethod
    def _get_or_create_record(db) -> DhanIncident:
        record = db.query(DhanIncident).filter(DhanIncident.provider == "dhan").first()
        if record:
            return record
        record = DhanIncident(provider="dhan", affected_consumers=[])
        db.add(record)
        db.flush()
        return record

    @staticmethod
    def _unhealthy_consumers(db) -> list[DhanConsumerState]:
        rows = db.query(DhanConsumerState).order_by(DhanConsumerState.consumer, DhanConsumerState.instance_id).all()
        return [row for row in rows if (row.state or "").strip().lower() not in HEALTHY_STATES]


dhan_incident_service = DhanIncidentService()
