"""
S&P 500 ticker retrieval.

Primary source: Wikipedia list (same approach as Chris' scanner).
Fallback: a small hard-coded list of the largest constituents so scans can
still run if the Wikipedia request fails.
"""

from __future__ import annotations

import logging
from functools import lru_cache

import pandas as pd
import requests

from bull.exceptions import TickerFetchError

log = logging.getLogger(__name__)

_WIKIPEDIA_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; bull-scanner/0.1; "
        "+https://github.com/kyleian/bull)"
    )
}

# Top-50 fallback so the scanner is never completely blind
_FALLBACK_TICKERS: list[str] = [
    "AAPL", "MSFT", "NVDA", "AMZN", "META", "GOOGL", "GOOG", "BRK-B",
    "LLY", "JPM", "V", "XOM", "UNH", "TSLA", "MA", "JNJ", "PG", "HD",
    "MRK", "COST", "ABBV", "CVX", "CRM", "NFLX", "KO", "AMD", "PEP",
    "WMT", "TMO", "LIN", "ADBE", "MCD", "DHR", "ACN", "CSCO", "ABT",
    "BAC", "AVGO", "TXN", "NKE", "NEE", "PM", "ORCL", "RTX", "QCOM",
    "MS", "GE", "HON", "AMGN", "IBM",
]


@lru_cache(maxsize=1)
def get_sp500_tickers() -> list[str]:
    """
    Return a deduplicated, sorted list of S&P 500 ticker symbols.

    Attempts to scrape the Wikipedia constituents table; falls back to a
    hard-coded list of the top-50 if the request fails.

    Returns
    -------
    list[str]
        Ticker symbols with dots replaced by hyphens (yfinance convention).

    Raises
    ------
    TickerFetchError
        Only raised when *both* Wikipedia *and* the fallback are unavailable
        (extremely unlikely).
    """
    try:
        log.debug("Fetching S&P 500 tickers from Wikipedia …")
        response = requests.get(_WIKIPEDIA_URL, headers=_HEADERS, timeout=15)
        response.raise_for_status()
        tables = pd.read_html(response.content)
        sp500_df = tables[0]
        tickers = sp500_df["Symbol"].tolist()
        tickers = [str(t).replace(".", "-").strip().upper() for t in tickers]
        log.info("Fetched %d S&P 500 tickers from Wikipedia.", len(tickers))
        return sorted(set(tickers))
    except Exception as exc:
        log.warning(
            "Wikipedia ticker fetch failed (%s). Using fallback list of %d tickers.",
            exc,
            len(_FALLBACK_TICKERS),
        )
        return sorted(set(_FALLBACK_TICKERS))
