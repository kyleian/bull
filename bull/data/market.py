"""
Market data fetching layer.

Wraps yfinance with:
  - Robust error handling (network, empty frame, delisted tickers)
  - Uniform DataFrame shape validation
  - Company metadata extraction (name, sector, description)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import pandas as pd
import yfinance as yf

from bull.config import settings
from bull.exceptions import InsufficientDataError, MarketDataError

log = logging.getLogger(__name__)


@dataclass(slots=True)
class MarketData:
    """All raw data for a single ticker ready for analysis."""

    ticker: str
    df: pd.DataFrame          # OHLCV history, date-indexed, timezone-naive UTC
    company_name: str = "Unknown"
    sector: str = "Unknown"
    description: str = ""


def fetch_market_data(ticker: str) -> MarketData:
    """
    Fetch OHLCV history and company metadata for *ticker*.

    Parameters
    ----------
    ticker:
        Ticker symbol (yfinance format, e.g. ``"BRK-B"``).

    Returns
    -------
    MarketData

    Raises
    ------
    MarketDataError
        Any network or parsing error that prevents data retrieval.
    InsufficientDataError
        When fewer rows than ``settings.min_history_rows`` are available.
    """
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period=f"{settings.history_days}d")
    except Exception as exc:
        raise MarketDataError(ticker, f"yfinance fetch failed: {exc}") from exc

    if df.empty:
        raise MarketDataError(ticker, "empty price history (possibly delisted)")

    # Normalise index — drop timezone so pandas arithmetic is uniform
    if hasattr(df.index, "tz") and df.index.tz is not None:
        df.index = df.index.tz_convert("UTC").tz_localize(None)

    if len(df) < settings.min_history_rows:
        raise InsufficientDataError(
            ticker,
            f"only {len(df)} rows available, need ≥ {settings.min_history_rows}",
        )

    # ── Company metadata (best-effort — never fatal) ──────────────────────────
    company_name = ticker
    sector = "Unknown"
    description = ""
    try:
        info = stock.info or {}
        company_name = info.get("shortName") or info.get("longName") or ticker
        sector = info.get("sector") or "Unknown"
        # Truncate long summaries to avoid bloating reports
        raw_desc = info.get("longBusinessSummary") or ""
        description = raw_desc[:400] + ("…" if len(raw_desc) > 400 else "")
    except Exception as exc:
        log.debug("[%s] metadata fetch failed (non-fatal): %s", ticker, exc)

    return MarketData(
        ticker=ticker,
        df=df,
        company_name=company_name,
        sector=sector,
        description=description,
    )
