from __future__ import annotations

import json
from datetime import datetime, timezone


def _quote(symbol: str, strike: int, option_type: str, ltp: float, oi: int) -> dict:
    return {
        "symbol": symbol,
        "security_id": f"{strike}{option_type}",
        "strike": strike,
        "option_type": option_type,
        "expiry": "2026-03-12",
        "ltp": ltp,
        "bid": round(ltp - 0.15, 2),
        "ask": round(ltp + 0.15, 2),
        "bid_qty": 450,
        "ask_qty": 470,
        "iv": 11.2,
        "oi": oi,
        "oi_lakhs": round(oi / 100000, 2),
        "volume": 25000,
        "delta": 0.42 if option_type == "CE" else -0.41,
        "gamma": 0.012,
        "theta": -8.4,
        "vega": 3.1,
    }


def build_chain(row_count: int = 81) -> dict:
    start_strike = 20500
    rows = []
    for idx in range(row_count):
        strike = start_strike + (idx * 50)
        call = _quote(f"NIFTY_2026-03-12_{strike}_CE", strike, "CE", max(8, 280 - idx * 2.7), 90000 + idx * 750)
        put = _quote(f"NIFTY_2026-03-12_{strike}_PE", strike, "PE", max(8, 70 + idx * 2.4), 95000 + idx * 720)
        rows.append(
            {
                "strike": strike,
                "is_atm": strike == 22500,
                "call": call,
                "put": put,
            }
        )
    return {
        "snapshot": {
            "spot_symbol": "NIFTY 50",
            "spot": 22512.35,
            "change": 104.2,
            "change_pct": 0.46,
            "vix": 14.2,
            "pcr": 1.04,
            "market_status": "OPEN",
            "expiries": ["2026-03-12"],
            "active_expiry": "2026-03-12",
            "degraded": False,
            "degraded_reason": None,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        },
        "rows": rows,
    }


def payload_size_bytes(payload: dict) -> int:
    return len(json.dumps(payload, separators=(",", ":")).encode("utf-8"))


def main() -> None:
    chain = build_chain()
    full_chain_event = {"type": "option.chain", "payload": chain}
    one_quote_delta = {
        "type": "option.quotes",
        "payload": {
            "active_expiry": "2026-03-12",
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "quotes": [chain["rows"][40]["call"]],
        },
    }
    ten_quote_delta = {
        "type": "option.quotes",
        "payload": {
            "active_expiry": "2026-03-12",
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "quotes": [row["call"] for row in chain["rows"][35:45]],
        },
    }

    full_bytes = payload_size_bytes(full_chain_event)
    one_delta_bytes = payload_size_bytes(one_quote_delta)
    ten_delta_bytes = payload_size_bytes(ten_quote_delta)
    poll_floor_ms = 5000
    feed_flush_ms = 150

    print("Synthetic latency benchmark")
    print("===========================")
    print(f"full_chain_event_bytes={full_bytes}")
    print(f"single_quote_delta_bytes={one_delta_bytes}")
    print(f"ten_quote_delta_bytes={ten_delta_bytes}")
    print(f"payload_reduction_single={(1 - (one_delta_bytes / full_bytes)) * 100:.2f}%")
    print(f"payload_reduction_ten={(1 - (ten_delta_bytes / full_bytes)) * 100:.2f}%")
    print(f"freshness_floor_before_ms={poll_floor_ms}")
    print(f"freshness_floor_after_ms={feed_flush_ms}")
    print(f"freshness_improvement_factor={poll_floor_ms / feed_flush_ms:.2f}x")
    print(f"row_render_scope_before={len(chain['rows'])}")
    print("row_render_scope_after=1")
    print(f"row_render_reduction={(1 - (1 / len(chain['rows']))) * 100:.2f}%")


if __name__ == "__main__":
    main()
