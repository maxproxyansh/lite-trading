from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timezone, timedelta

IST = timezone(timedelta(hours=5, minutes=30))
REGULAR_MARKET_OPEN = time(hour=9, minute=15)
REGULAR_MARKET_CLOSE = time(hour=15, minute=30)
ORDER_WINDOW_TEXT = "9:15 AM to 3:30 PM IST"

# Official NSE F&O holidays for calendar year 2026. Muhurat trading is announced separately.
NSE_FO_TRADING_HOLIDAYS: dict[int, dict[date, str]] = {
    2026: {
        date(2026, 1, 26): "Republic Day",
        date(2026, 2, 15): "Mahashivratri",
        date(2026, 3, 6): "Holi",
        date(2026, 3, 26): "Shri Ram Navami",
        date(2026, 4, 3): "Good Friday",
        date(2026, 4, 14): "Dr. Baba Saheb Ambedkar Jayanti",
        date(2026, 5, 1): "Maharashtra Day",
        date(2026, 8, 15): "Independence Day / Parsi New Year",
        date(2026, 8, 27): "Ganesh Chaturthi",
        date(2026, 10, 2): "Mahatma Gandhi Jayanti / Dussehra",
        date(2026, 11, 10): "Diwali Balipratipada",
        date(2026, 11, 15): "Guru Nanak Jayanti",
        date(2026, 12, 25): "Christmas",
    },
}


@dataclass(frozen=True)
class MarketSession:
    status: str
    is_open: bool
    reason: str | None = None
    holiday_name: str | None = None


def now_ist() -> datetime:
    return datetime.now(IST)


def holiday_name(day: date) -> str | None:
    return NSE_FO_TRADING_HOLIDAYS.get(day.year, {}).get(day)


def _format_clock(value: time) -> str:
    hour = value.hour % 12 or 12
    meridiem = "AM" if value.hour < 12 else "PM"
    return f"{hour}:{value.minute:02d} {meridiem}"


def market_session(moment: datetime | None = None) -> MarketSession:
    now = moment.astimezone(IST) if moment is not None else now_ist()
    holiday = holiday_name(now.date())
    if holiday:
        return MarketSession(
            status="HOLIDAY",
            is_open=False,
            holiday_name=holiday,
            reason=(
                f"Order rejected: NSE F&O is closed on {now.strftime('%B %d, %Y')} for {holiday}. "
                f"Lite accepts orders only on trading days between {ORDER_WINDOW_TEXT}."
            ),
        )

    if now.weekday() >= 5:
        return MarketSession(
            status="CLOSED",
            is_open=False,
            reason=(
                f"Order rejected: NSE F&O is closed on weekends. "
                f"Lite accepts orders only on trading days between {ORDER_WINDOW_TEXT}."
            ),
        )

    market_open = now.replace(
        hour=REGULAR_MARKET_OPEN.hour,
        minute=REGULAR_MARKET_OPEN.minute,
        second=0,
        microsecond=0,
    )
    market_close = now.replace(
        hour=REGULAR_MARKET_CLOSE.hour,
        minute=REGULAR_MARKET_CLOSE.minute,
        second=0,
        microsecond=0,
    )

    if market_open <= now <= market_close:
        return MarketSession(status="OPEN", is_open=True)

    if now < market_open:
        pre_open_start = now.replace(hour=9, minute=0, second=0, microsecond=0)
        status = "PRE-OPEN" if pre_open_start <= now < market_open else "CLOSED"
        return MarketSession(
            status=status,
            is_open=False,
            reason=(
                f"Order rejected: NSE F&O regular trading starts at {_format_clock(REGULAR_MARKET_OPEN)} IST. "
                "Lite does not support pre-open or after-market order entry."
            ),
        )

    return MarketSession(
        status="CLOSED",
        is_open=False,
        reason=(
            f"Order rejected: NSE F&O regular trading closed at {_format_clock(REGULAR_MARKET_CLOSE)} IST. "
            f"Lite accepts orders only on trading days between {ORDER_WINDOW_TEXT}."
        ),
    )


def is_market_open() -> bool:
    return market_session().is_open


def market_status() -> str:
    return market_session().status


def order_entry_rejection_reason() -> str | None:
    session = market_session()
    return None if session.is_open else session.reason
