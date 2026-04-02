"""
Ticker universe retrieval.

Supported universes
-------------------
sp500        ~503 tickers — Wikipedia / fallback top-50
nasdaq100    ~101 tickers — Wikipedia / fallback top-25
dow30           30 tickers — hard-coded (stable list)
etf             ~50 curated ETFs across sectors/asset classes
mutual_fund     ~20 curated large US mutual funds
all             union of all universes above

Primary sources: Wikipedia (same approach as Chris' scanner).
Fallbacks: hard-coded lists so scans still run if web requests fail.
"""

from __future__ import annotations

import logging
from functools import lru_cache

import pandas as pd
import requests

from bull.exceptions import TickerFetchError

log = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; bull-scanner/0.1; "
        "+https://github.com/kyleian/bull)"
    )
}

# ── S&P 500 ──────────────────────────────────────────────────────────────────

_SP500_WIKI = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"

_SP500_FALLBACK: list[str] = [
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
    """
    try:
        log.debug("Fetching S&P 500 tickers from Wikipedia …")
        resp = requests.get(_SP500_WIKI, headers=_HEADERS, timeout=15)
        resp.raise_for_status()
        tables = pd.read_html(resp.content)
        tickers = [str(t).replace(".", "-").strip().upper() for t in tables[0]["Symbol"].tolist()]
        log.info("Fetched %d S&P 500 tickers from Wikipedia.", len(tickers))
        return sorted(set(tickers))
    except Exception as exc:
        log.warning("S&P 500 Wikipedia fetch failed (%s). Using fallback.", exc)
        return sorted(set(_SP500_FALLBACK))


# ── NASDAQ 100 ────────────────────────────────────────────────────────────────

_NASDAQ100_WIKI = "https://en.wikipedia.org/wiki/Nasdaq-100"

_NASDAQ100_FALLBACK: list[str] = [
    "AAPL", "MSFT", "NVDA", "AMZN", "META", "GOOGL", "GOOG", "TSLA",
    "AVGO", "COST", "NFLX", "AMD", "ADBE", "PEP", "CSCO", "TMUS",
    "TXN", "QCOM", "INTC", "INTU", "AMGN", "HON", "AMAT", "BKNG",
    "MU",
]


@lru_cache(maxsize=1)
def get_nasdaq100_tickers() -> list[str]:
    """Return a deduplicated, sorted list of NASDAQ-100 ticker symbols."""
    try:
        log.debug("Fetching NASDAQ-100 tickers from Wikipedia …")
        resp = requests.get(_NASDAQ100_WIKI, headers=_HEADERS, timeout=15)
        resp.raise_for_status()
        tables = pd.read_html(resp.content)
        # Find the table that has a 'Ticker' or 'Symbol' column
        for tbl in tables:
            cols = [str(c).strip() for c in tbl.columns]
            for col in ("Ticker", "Symbol", "ticker", "symbol"):
                if col in cols:
                    tickers = [str(t).replace(".", "-").strip().upper() for t in tbl[col].tolist()]
                    tickers = [t for t in tickers if t and not t.startswith("NAN")]
                    log.info("Fetched %d NASDAQ-100 tickers from Wikipedia.", len(tickers))
                    return sorted(set(tickers))
        raise ValueError("No ticker column found in NASDAQ-100 Wikipedia tables.")
    except Exception as exc:
        log.warning("NASDAQ-100 Wikipedia fetch failed (%s). Using fallback.", exc)
        return sorted(set(_NASDAQ100_FALLBACK))


# ── Dow Jones 30 ──────────────────────────────────────────────────────────────

_DOW30: list[str] = [
    "AAPL", "AMGN", "AXP", "BA", "CAT", "CRM", "CSCO", "CVX", "DIS",
    "DOW", "GS", "HD", "HON", "IBM", "JNJ", "JPM", "KO", "MCD", "MMM",
    "MRK", "MSFT", "NKE", "PG", "SHW", "TRV", "UNH", "V", "VZ", "WMT",
    "WBA",
]


def get_dow30_tickers() -> list[str]:
    """Return the 30 Dow Jones Industrial Average constituents."""
    return sorted(_DOW30)


# ── ETFs ──────────────────────────────────────────────────────────────────────

_ETFS: list[str] = [
    # Broad market
    "SPY", "IVV", "VOO", "VTI", "ITOT", "SCHB",
    # NASDAQ / growth
    "QQQ", "QQQM", "VUG", "SCHG",
    # Small / mid cap
    "IWM", "IJH", "VXF",
    # Dow Jones
    "DIA",
    # International
    "EFA", "VEA", "VWO", "EEM",
    # Fixed income / bonds
    "TLT", "IEF", "SHY", "AGG", "BND", "LQD", "HYG",
    # Commodities
    "GLD", "IAU", "SLV", "USO", "UNG",
    # Real estate
    "VNQ", "IYR",
    # Volatility
    "VXX", "UVXY",
    # Sector ETFs (SPDR)
    "XLK", "XLF", "XLE", "XLV", "XLC", "XLI", "XLY", "XLP", "XLU", "XLB", "XLRE",
    # Thematic / innovation
    "ARKK", "ARKG", "ARKF", "ARKQ",
    # Semiconductors
    "SOXX", "SMH",
    # Biotech
    "IBB", "XBI",
    # Dividends
    "VIG", "SCHD",
    # Leveraged (2×/3×)
    "TQQQ", "SQQQ", "SPXL", "SPXS",
]


def get_etf_tickers() -> list[str]:
    """Return a curated list of major ETF ticker symbols."""
    return sorted(_ETFS)


# ── Mutual Funds ──────────────────────────────────────────────────────────────

_MUTUAL_FUNDS: list[str] = [
    # Fidelity
    "FXAIX",   # Fidelity 500 Index
    "FSKAX",   # Fidelity Total Market Index
    "FCNTX",   # Fidelity Contrafund
    "FGRIX",   # Fidelity Growth & Income
    "FDGRX",   # Fidelity Growth Company
    "FPURX",   # Fidelity Puritan
    "FBALX",   # Fidelity Balanced
    # Vanguard
    "VFIAX",   # Vanguard 500 Index Admiral
    "VTSAX",   # Vanguard Total Stock Market
    "VWELX",   # Vanguard Wellington
    "VWINX",   # Vanguard Wellesley Income
    "VDIGX",   # Vanguard Dividend Growth
    # T. Rowe Price
    "PRGFX",   # T. Rowe Price Growth Stock
    "PRWCX",   # T. Rowe Price Capital Appreciation
    "TRBCX",   # T. Rowe Price Blue Chip Growth
    # American Funds
    "AGTHX",   # American Funds Growth Fund of America
    "ABALX",   # American Funds American Balanced
    # Dodge & Cox
    "DODGX",   # Dodge & Cox Stock Fund
    # Primecap
    "POAGX",   # Primecap Odyssey Aggressive Growth
    # Schwab
    "SWPPX",   # Schwab S&P 500 Index
]


def get_mutual_fund_tickers() -> list[str]:
    """Return a curated list of large US mutual fund ticker symbols."""
    return sorted(_MUTUAL_FUNDS)


# ── Universe dispatcher ───────────────────────────────────────────────────────

#: Valid universe names accepted by get_tickers_for_universe()
UNIVERSE_NAMES: tuple[str, ...] = (
    "sp500", "nasdaq100", "dow30", "etf", "mutual_fund", "all",
)


def get_tickers_for_universe(universe: str) -> list[str]:
    """
    Return a deduplicated, sorted ticker list for the requested universe.

    Parameters
    ----------
    universe:
        One of ``sp500``, ``nasdaq100``, ``dow30``, ``etf``,
        ``mutual_fund``, or ``all``.

    Raises
    ------
    ValueError
        If *universe* is not a recognised name.
    """
    universe = universe.lower().strip()
    if universe == "sp500":
        return get_sp500_tickers()
    if universe == "nasdaq100":
        return get_nasdaq100_tickers()
    if universe == "dow30":
        return get_dow30_tickers()
    if universe == "etf":
        return get_etf_tickers()
    if universe == "mutual_fund":
        return get_mutual_fund_tickers()
    if universe == "all":
        combined = (
            get_sp500_tickers()
            + get_nasdaq100_tickers()
            + get_dow30_tickers()
            + get_etf_tickers()
            + get_mutual_fund_tickers()
        )
        return sorted(set(combined))
    raise ValueError(
        f"Unknown universe {universe!r}. "
        f"Valid options: {', '.join(UNIVERSE_NAMES)}"
    )
