"""FII/DII participant-wise OI data service.

Fetches daily participant CSV from NSE archives, parses it, and caches
results in memory (data only changes once a day after market close).
"""
from __future__ import annotations

import csv
import io
import logging
from datetime import datetime, timedelta
from typing import Any

import requests

logger = logging.getLogger(__name__)

_NSE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Referer": "https://www.nseindia.com",
}

_NSE_URL_PATTERN = "https://archives.nseindia.com/content/nsccl/fao_participant_oi_{date}.csv"

# In-memory cache: date string -> parsed snapshot dict
_cache: dict[str, dict[str, Any]] = {}


def _safe_int(val: Any) -> int:
    try:
        return int(str(val).strip().replace(",", ""))
    except (ValueError, TypeError):
        return 0


def _business_days_back(n: int, from_date: datetime | None = None) -> list[datetime]:
    """Return up to *n* business days ending at *from_date* (inclusive), most recent first."""
    base = from_date or datetime.now()
    days: list[datetime] = []
    i = 0
    while len(days) < n:
        d = base - timedelta(days=i)
        if d.weekday() < 5:
            days.append(d)
        i += 1
        if i > n + 20:
            break
    return days


def _fetch_csv_text(d: datetime) -> str | None:
    """Try to download the participant CSV for a given date. Returns text or None."""
    date_str = d.strftime("%d%m%Y")
    url = _NSE_URL_PATTERN.format(date=date_str)
    try:
        resp = requests.get(url, headers=_NSE_HEADERS, timeout=10)
        if resp.status_code == 200 and len(resp.text.strip()) > 50:
            return resp.text
        logger.debug("NSE participant CSV %s returned status %s", date_str, resp.status_code)
    except requests.RequestException as exc:
        logger.warning("Failed to fetch NSE participant CSV for %s: %s", date_str, exc)
    return None


def _parse_csv(text: str, d: datetime) -> dict[str, Any] | None:
    """Parse participant-wise OI CSV into structured dict.

    CSV layout (row 0 is a title, row 1 is actual header, rows 2+ are data):
        Client Type | Future Index Long | Future Index Short |
        Future Stock Long | Future Stock Short |
        Option Index Call Long | Option Index Put Long |
        Option Index Call Short | Option Index Put Short |
        Option Stock Call Long | Option Stock Put Long |
        Option Stock Call Short | Option Stock Put Short |
        Total Long Contracts | Total Short Contracts
    """
    try:
        lines = text.strip().splitlines()
        if len(lines) < 3:
            return None

        # Skip title row, use row 1 as header
        reader = csv.reader(lines[1:])
        headers_raw = next(reader)
        headers = [h.strip().lower() for h in headers_raw]

        def find_col(*keywords: str) -> int | None:
            for i, name in enumerate(headers):
                if all(k in name for k in keywords):
                    return i
            return None

        idx_fut_long = find_col("future", "index", "long")
        idx_fut_short = find_col("future", "index", "short")
        idx_opt_call_long = find_col("option", "index", "call", "long")
        idx_opt_put_long = find_col("option", "index", "put", "long")
        idx_opt_call_short = find_col("option", "index", "call", "short")
        idx_opt_put_short = find_col("option", "index", "put", "short")

        rows: dict[str, list[str]] = {}
        for row in reader:
            if not row:
                continue
            client_type = row[0].strip().upper()
            if client_type in ("FII", "DII", "PRO", "CLIENT") or "FOREIGN" in client_type or "FPI" in client_type:
                # Normalize label
                if "FOREIGN" in client_type or "FPI" in client_type:
                    rows["FII"] = row
                elif "DOMESTIC" in client_type:
                    rows["DII"] = row
                elif "PROPRIETARY" in client_type:
                    rows["PRO"] = row
                elif "RETAIL" in client_type:
                    rows["CLIENT"] = row
                else:
                    rows[client_type] = row

        def get_val(row: list[str] | None, col_idx: int | None) -> int:
            if row is None or col_idx is None or col_idx >= len(row):
                return 0
            return _safe_int(row[col_idx])

        def extract(row: list[str] | None) -> dict[str, int]:
            fut_long = get_val(row, idx_fut_long)
            fut_short = get_val(row, idx_fut_short)
            return {
                "fut_long": fut_long,
                "fut_short": fut_short,
                "net_futures": fut_long - fut_short,
                "opt_call_long": get_val(row, idx_opt_call_long),
                "opt_call_short": get_val(row, idx_opt_call_short),
                "opt_put_long": get_val(row, idx_opt_put_long),
                "opt_put_short": get_val(row, idx_opt_put_short),
            }

        snapshot = {
            "date": d.strftime("%Y-%m-%d"),
            "fii": extract(rows.get("FII")),
            "dii": extract(rows.get("DII")),
            "pro": extract(rows.get("PRO")),
            "client": extract(rows.get("CLIENT")),
        }

        logger.info(
            "Participant data for %s — FII net=%d, DII net=%d, PRO net=%d, Client net=%d",
            d.strftime("%Y-%m-%d"),
            snapshot["fii"]["net_futures"],
            snapshot["dii"]["net_futures"],
            snapshot["pro"]["net_futures"],
            snapshot["client"]["net_futures"],
        )
        return snapshot

    except Exception as exc:
        logger.error("Error parsing participant CSV for %s: %s", d.strftime("%Y-%m-%d"), exc)
        return None


def _fetch_and_cache(d: datetime) -> dict[str, Any] | None:
    """Fetch, parse, cache a single date. Returns snapshot or None."""
    date_key = d.strftime("%Y-%m-%d")
    if date_key in _cache:
        return _cache[date_key]

    text = _fetch_csv_text(d)
    if text is None:
        return None

    snapshot = _parse_csv(text, d)
    if snapshot is not None:
        _cache[date_key] = snapshot
    return snapshot


def get_latest() -> dict[str, Any] | None:
    """Return the most recent available participant snapshot.

    Tries today first, then previous 5 business days.
    """
    for d in _business_days_back(6):
        snapshot = _fetch_and_cache(d)
        if snapshot is not None:
            return snapshot
    logger.error("Could not fetch participant data for any recent date")
    return None


def get_history(days: int = 30) -> list[dict[str, Any]]:
    """Return participant snapshots for the last *days* business days.

    Results are ordered oldest-first for charting convenience.
    Uncached dates are fetched in parallel for speed.
    """
    dates = _business_days_back(days)

    # Split into cached hits and uncached misses
    snapshots_by_date: dict[str, dict[str, Any]] = {}
    uncached: list[datetime] = []
    for d in dates:
        date_key = d.strftime("%Y-%m-%d")
        if date_key in _cache:
            snapshots_by_date[date_key] = _cache[date_key]
        else:
            uncached.append(d)

    # Fetch uncached dates in parallel
    if uncached:
        from concurrent.futures import ThreadPoolExecutor, as_completed
        with ThreadPoolExecutor(max_workers=10) as pool:
            futures = {pool.submit(_fetch_and_cache, d): d for d in uncached}
            for future in as_completed(futures):
                result = future.result()
                if result is not None:
                    snapshots_by_date[result["date"]] = result

    # Build result in oldest-first order
    snapshots: list[dict[str, Any]] = []
    for d in reversed(dates):
        date_key = d.strftime("%Y-%m-%d")
        if date_key in snapshots_by_date:
            snapshots.append(snapshots_by_date[date_key])
    return snapshots
