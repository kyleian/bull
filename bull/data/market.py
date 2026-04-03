"""
Market data fetching -- provider dispatcher.

Selects the backend based on BULL_DATA_PROVIDER:
  yfinance  (default) -- free, ~60 req/min rate limit, no key needed
  tiingo              -- $10/mo Starter, unlimited EOD + news
                        Sign up: https://www.tiingo.com/account/api/token
                        Set BULL_TIINGO_API_KEY=<your_key> in .env

Both providers return the same MarketData interface so the rest of the
codebase is completely provider-agnostic.
"""

from __future__ import annotations

import logging

from bull.config import DataProvider, settings
from bull.data.providers.base import MarketData  # re-export for backwards compat
from bull.exceptions import MarketDataError

log = logging.getLogger(__name__)

_provider = None
_yf_fallback = None


def _get_provider():
    global _provider
    if _provider is None:
        if settings.data_provider == DataProvider.TIINGO:
            if not settings.tiingo_api_key:
                log.warning(
                    "BULL_DATA_PROVIDER=tiingo but BULL_TIINGO_API_KEY is not set. "
                    "Falling back to yfinance. "
                    "Get your key at https://www.tiingo.com/account/api/token"
                )
                from bull.data.providers.yfinance_provider import YFinanceProvider
                _provider = YFinanceProvider()
            else:
                from bull.data.providers.tiingo_provider import TiingoProvider
                _provider = TiingoProvider()
                log.info("Using Tiingo data provider.")
        else:
            from bull.data.providers.yfinance_provider import YFinanceProvider
            _provider = YFinanceProvider()
    return _provider


def _get_yf_fallback():
    global _yf_fallback
    if _yf_fallback is None:
        from bull.data.providers.yfinance_provider import YFinanceProvider
        _yf_fallback = YFinanceProvider()
    return _yf_fallback


def fetch_market_data(ticker: str) -> MarketData:
    """
    Fetch OHLCV history and company metadata for *ticker*.

    Delegates to the configured provider (yfinance or Tiingo).
    If Tiingo returns a 429 rate-limit error, automatically falls back
    to yfinance for that ticker so the scan continues uninterrupted.

    Raises
    ------
    MarketDataError / InsufficientDataError
        Propagated from the active provider.
    """
    provider = _get_provider()
    try:
        return provider.fetch(ticker)
    except MarketDataError as exc:
        # Transparent yfinance fallback on Tiingo rate-limit (429)
        if settings.data_provider == DataProvider.TIINGO and "429" in str(exc):
            log.debug("[%s] Tiingo rate-limited; falling back to yfinance.", ticker)
            return _get_yf_fallback().fetch(ticker)
        raise


__all__ = ["fetch_market_data", "MarketData"]
