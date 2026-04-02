"""
Data provider package.

BULL_DATA_PROVIDER env var selects the backend:
  yfinance  (default) — free, rate-limited, no key required
  tiingo              — $10/mo, unlimited EOD + news, key required
"""
from bull.data.providers.base import BaseProvider, MarketData  # noqa: F401
