"""
yfinance-backed data provider.

Free, no API key, but Yahoo Finance rate-limits aggressive polling (~60 req/min).
Falls back automatically for any ticker not handled by the primary provider.
"""

from __future__ import annotations

import logging

import pandas as pd
import yfinance as yf

from bull.config import settings
from bull.data.providers.base import BaseProvider, MarketData
from bull.exceptions import InsufficientDataError, MarketDataError

log = logging.getLogger(__name__)


class YFinanceProvider(BaseProvider):
    """Wraps yfinance with uniform error handling + metadata extraction."""

    def fetch(self, ticker: str) -> MarketData:
        try:
            stock = yf.Ticker(ticker)
            df = stock.history(period=f"{settings.history_days}d")
        except Exception as exc:
            raise MarketDataError(ticker, f"yfinance fetch failed: {exc}") from exc

        if df.empty:
            raise MarketDataError(ticker, "empty price history (possibly delisted)")

        # Normalise index to timezone-naive UTC
        if hasattr(df.index, "tz") and df.index.tz is not None:
            df.index = df.index.tz_convert("UTC").tz_localize(None)

        if len(df) < settings.min_history_rows:
            raise InsufficientDataError(
                ticker,
                f"only {len(df)} rows, need >= {settings.min_history_rows}",
            )

        company_name = ticker
        sector = "Unknown"
        description = ""
        news_headlines: list[str] = []

        try:
            info = stock.info or {}
            company_name = info.get("shortName") or info.get("longName") or ticker
            sector = info.get("sector") or "Unknown"
            raw_desc = info.get("longBusinessSummary") or ""
            description = raw_desc[:400] + ("..." if len(raw_desc) > 400 else "")
        except Exception as exc:
            log.debug("[%s] yfinance metadata failed (non-fatal): %s", ticker, exc)

        try:
            raw_news = stock.news or []
            news_headlines = [
                n.get("content", {}).get("title", "") or n.get("title", "")
                for n in raw_news[:10]
                if n
            ]
            news_headlines = [h for h in news_headlines if h]
        except Exception as exc:
            log.debug("[%s] yfinance news fetch failed (non-fatal): %s", ticker, exc)

        return MarketData(
            ticker=ticker,
            df=df,
            company_name=company_name,
            sector=sector,
            description=description,
            news_headlines=news_headlines,
        )
