"""
Tiingo-backed data provider.

Sign up at https://www.tiingo.com/account/api/token
Starter plan: $10/month — unlimited EOD requests, news API, mutual fund support.
Set BULL_TIINGO_API_KEY in your .env file to activate.

API docs: https://www.tiingo.com/documentation/general/overview
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from functools import lru_cache

import pandas as pd
import requests

from bull.config import settings
from bull.data.providers.base import BaseProvider, MarketData
from bull.exceptions import InsufficientDataError, MarketDataError

log = logging.getLogger(__name__)

_BASE_URL = "https://api.tiingo.com"
_SESSION = requests.Session()
_SESSION.headers.update({"Content-Type": "application/json"})


def _headers() -> dict:
    return {"Authorization": f"Token {settings.tiingo_api_key}"}


class TiingoProvider(BaseProvider):
    """
    Tiingo REST API provider.

    Covers: US equities, ETFs, mutual funds (daily NAV).
    Rate limits: none on Starter plan for EOD data.
    """

    def fetch(self, ticker: str) -> MarketData:
        # ── Price history ─────────────────────────────────────────────────────
        start = (date.today() - timedelta(days=settings.history_days + 10)).isoformat()

        try:
            resp = _SESSION.get(
                f"{_BASE_URL}/tiingo/daily/{ticker}/prices",
                params={"startDate": start, "resampleFreq": "daily"},
                headers=_headers(),
                timeout=15,
            )
            resp.raise_for_status()
            prices = resp.json()
        except Exception as exc:
            raise MarketDataError(ticker, f"Tiingo fetch failed: {exc}") from exc

        if not prices:
            raise MarketDataError(ticker, "Tiingo returned empty price history")

        df = pd.DataFrame(prices)
        df["date"] = pd.to_datetime(df["date"]).dt.tz_convert("UTC").dt.tz_localize(None)
        df = df.sort_values("date").set_index("date")

        # Rename to standard OHLCV column names expected by technical.py
        col_map = {
            "adjOpen": "Open",
            "adjHigh": "High",
            "adjLow": "Low",
            "adjClose": "Close",
            "adjVolume": "Volume",
        }
        # Prefer adjusted columns; fall back to unadjusted if missing
        for src, dst in col_map.items():
            if src in df.columns:
                df[dst] = df[src]
            elif dst.lower() in df.columns and dst not in df.columns:
                df[dst] = df[dst.lower()]

        required = {"Open", "High", "Low", "Close", "Volume"}
        missing = required - set(df.columns)
        if missing:
            raise MarketDataError(ticker, f"Tiingo response missing columns: {missing}")

        if len(df) < settings.min_history_rows:
            raise InsufficientDataError(
                ticker,
                f"only {len(df)} rows, need >= {settings.min_history_rows}",
            )

        # ── Metadata ──────────────────────────────────────────────────────────
        company_name = ticker
        sector = "Unknown"
        description = ""
        try:
            meta = _fetch_meta(ticker)
            company_name = meta.get("name") or ticker
            description = (meta.get("description") or "")[:400]
            # Tiingo doesn't provide sector in free tier; leave as Unknown
            # (yfinance can supplement if needed as fallback)
        except Exception as exc:
            log.debug("[%s] Tiingo metadata failed (non-fatal): %s", ticker, exc)

        # ── News ──────────────────────────────────────────────────────────────
        news_headlines: list[str] = []
        try:
            news_headlines = _fetch_news(ticker)
        except Exception as exc:
            log.debug("[%s] Tiingo news failed (non-fatal): %s", ticker, exc)

        return MarketData(
            ticker=ticker,
            df=df,
            company_name=company_name,
            sector=sector,
            description=description,
            news_headlines=news_headlines,
        )


@lru_cache(maxsize=512)
def _fetch_meta(ticker: str) -> dict:
    resp = _SESSION.get(
        f"{_BASE_URL}/tiingo/daily/{ticker}",
        headers=_headers(),
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


@lru_cache(maxsize=256)
def _fetch_news(ticker: str, limit: int = 10) -> list[str]:
    """Return up to *limit* recent news headlines for *ticker* from Tiingo."""
    resp = _SESSION.get(
        f"{_BASE_URL}/tiingo/news",
        params={"tickers": ticker, "limit": limit},
        headers=_headers(),
        timeout=10,
    )
    resp.raise_for_status()
    articles = resp.json() or []
    return [a.get("title", "") for a in articles if a.get("title")]
