"""Tests for feed latency fixes — per-packet DB write elimination."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def service():
    """Create a MarketDataService with mocked dependencies."""
    with (
        patch("services.market_data.dhan_credential_service") as mock_creds,
        patch("services.market_data.dhan_incident_service") as mock_incidents,
    ):
        mock_creds.snapshot.return_value = MagicMock(
            configured=True,
            client_id="test",
            access_token="test",
            data_plan_status="active",
        )
        mock_creds.configured.return_value = True
        mock_incidents.set_provider_health = MagicMock()

        from services.market_data import MarketDataService

        svc = MarketDataService()
        svc._health.last_option_chain_success_at = datetime.now(timezone.utc)
        svc._health.last_feed_message_at = datetime.now(timezone.utc)
        yield svc, mock_incidents


class TestCloseIncidentNoOpWhenHealthy:
    """_close_incident should skip DB write when no incident is open and DB is already synced."""

    @pytest.mark.asyncio
    async def test_first_healthy_call_syncs_db(self, service):
        """First call after startup MUST write to DB (clears stale crash state)."""
        svc, mock_incidents = service
        assert svc._health_synced_to_db is False

        await svc._close_incident()

        mock_incidents.set_provider_health.assert_called_once()
        assert svc._health_synced_to_db is True

    @pytest.mark.asyncio
    async def test_subsequent_healthy_calls_skip_db(self, service):
        """After first sync, healthy calls must NOT write to DB."""
        svc, mock_incidents = service
        svc._health_synced_to_db = True

        await svc._close_incident()

        mock_incidents.set_provider_health.assert_not_called()

    @pytest.mark.asyncio
    async def test_incident_close_always_writes_db(self, service):
        """When a real incident is open, closing it MUST write to DB."""
        svc, mock_incidents = service
        svc._health.incident_open = True
        svc._health.incident_reason = "REALTIME_FEED_STALE"
        svc._health_synced_to_db = True  # already synced before

        await svc._close_incident()

        mock_incidents.set_provider_health.assert_called_once()
        assert svc._health.incident_open is False
        assert svc._health_synced_to_db is True

    @pytest.mark.asyncio
    async def test_flag_resets_when_incident_opens(self, service):
        """Opening an incident should reset the sync flag so the next close writes to DB."""
        svc, mock_incidents = service
        svc._health_synced_to_db = True

        await svc._open_incident("REALTIME_FEED_STALE", "test")

        assert svc._health_synced_to_db is False


class TestDirtySymbolsPreservedAcrossRefresh:
    """_apply_chain_payload must NOT clear _dirty_quote_symbols."""

    def test_dirty_symbols_survive_chain_apply(self, service):
        """Live WebSocket updates marked dirty before REST refresh must not be lost."""
        svc, _ = service
        # Simulate live ticks dirtying symbols
        svc._dirty_quote_symbols.add("NIFTY_2026-03-27_23500_CE")
        svc._dirty_quote_symbols.add("NIFTY_2026-03-27_23500_PE")
        svc._pcr_dirty = True

        # Simulate REST refresh applying chain
        chain = {
            "quotes": {},
            "security_id_to_symbol": {},
            "rows": [],
            "spot": 23500.0,
            "total_call_oi": 100.0,
            "total_put_oi": 200.0,
        }
        svc._apply_chain_payload(chain, expiry="2026-03-27", now=datetime.now(timezone.utc))

        # Dirty symbols must still be present for next flush cycle
        assert "NIFTY_2026-03-27_23500_CE" in svc._dirty_quote_symbols
        assert "NIFTY_2026-03-27_23500_PE" in svc._dirty_quote_symbols
        assert svc._pcr_dirty is True
