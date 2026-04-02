"""
Ticker universe retrieval.

Supported universes
-------------------
sp500        ~503 tickers  — Wikipedia / fallback top-50
nasdaq100    ~101 tickers  — Wikipedia / fallback top-25
dow30           30 tickers — hard-coded (stable list)
etf             ~59 tickers — curated ETFs across sectors/asset classes
mutual_fund     ~20 tickers — curated large US mutual funds
russell2000  ~2000 tickers — iShares IWM holdings CSV / fallback top-100
adr             ~70 tickers — curated major American Depositary Receipts
crypto          ~25 tickers — major cryptocurrencies (yfinance BTC-USD format)
all           union of all universes above

Primary sources: Wikipedia (equities), iShares CSV (Russell), hard-coded (rest).
Fallbacks: hard-coded lists so scans still run if web requests fail.
"""

from __future__ import annotations

import io
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
        tables = pd.read_html(io.StringIO(resp.text))
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
        tables = pd.read_html(io.StringIO(resp.text))
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


# ── Russell 2000 ─────────────────────────────────────────────────────────────
# Primary: iShares IWM holdings CSV (public download, no auth required).
# Fallback: curated list of ~100 liquid small-cap names.

_IWM_CSV_URL = (
    "https://www.ishares.com/us/products/239710/ISHARES-RUSSELL-2000-ETF/"
    "1467271812956.ajax?fileType=csv&fileName=IWM_holdings&dataType=fund"
)

_RUSSELL2000_FALLBACK: list[str] = [
    # Technology
    "APPF", "CWAN", "STER", "TASK", "JAMF", "ALKT", "BAND", "NCNO",
    "COUR", "HUBS", "BRZE", "DOCN", "PCTY", "CFLT", "DOMO",
    # Healthcare  
    "ACAD", "AMPH", "ARWR", "AXSM", "BCYC", "BDTX", "BEAM", "BMRN",
    "CRNX", "DNLI", "DVAX", "FATE", "FOLD", "HALO", "IMVT", "INVA",
    "IONS", "IOVA", "KRYS", "LGND", "MGNX", "NKTR", "NTLA", "OSPN",
    # Financials
    "BANF", "CATY", "CVBF", "EWBC", "FBIZ", "FFIN", "FULT", "HBCP",
    "HTLF", "IBCP", "INDB", "NBTB", "OFG", "PACW", "PRAA", "RBB",
    # Consumer
    "BOOT", "BJ", "CAKE", "CHUY", "CRAI", "DENN", "EAT", "FAT",
    "FRPT", "JACK", "KRUS", "LOCO", "NATH", "PLNT", "RAVE", "RUTH",
    # Industrials
    "AAON", "AEIS", "ALRM", "ARCB", "AZZ", "BWXT", "CEVA", "CHRD",
    "CIR", "CLB", "CNXN", "CORT", "DRD", "DXPE", "ECTM", "EFSC",
    # Energy
    "AMPY", "CIVI", "CKH", "CLR", "CNEY", "CRGY", "DCP", "ESSE",
    "FLNG", "GATO", "GEL", "GPP", "HOLX", "INFR", "KALU", "KFRC",
    # Materials
    "ASIX", "ATR", "BCC", "BCPC", "CENX", "CMC", "CSWI", "HCC",
    "IOSP", "KOP", "LTHM", "MFIN", "MTRX", "NACCO", "NN", "NX",
]


@lru_cache(maxsize=1)
def get_russell2000_tickers() -> list[str]:
    """
    Return Russell 2000 constituents.

    Primary: iShares IWM holdings CSV download.
    Fallback: curated list of ~100 liquid small-cap tickers.
    """
    try:
        log.debug("Fetching Russell 2000 from iShares IWM holdings CSV...")
        resp = requests.get(_IWM_CSV_URL, headers=_HEADERS, timeout=20)
        resp.raise_for_status()
        # iShares CSV has metadata rows before the actual data
        # Skip rows until we find a "Ticker" header
        lines = resp.text.splitlines()
        header_idx = None
        for i, line in enumerate(lines):
            if "Ticker" in line and "Name" in line:
                header_idx = i
                break
        if header_idx is None:
            raise ValueError("Could not find Ticker header in IWM CSV")
        csv_text = "\n".join(lines[header_idx:])
        df = pd.read_csv(io.StringIO(csv_text))
        tickers = [
            str(t).replace(".", "-").strip().upper()
            for t in df["Ticker"].dropna().tolist()
            if str(t).strip() not in ("-", "", "nan")
        ]
        log.info("Fetched %d Russell 2000 tickers from iShares IWM.", len(tickers))
        return sorted(set(tickers))
    except Exception as exc:
        log.warning("Russell 2000 iShares fetch failed (%s). Using fallback.", exc)
        return sorted(set(_RUSSELL2000_FALLBACK))


# ── American Depositary Receipts (ADRs) ──────────────────────────────────────
# Major international companies traded on US exchanges as ADRs.

_ADRS: list[str] = [
    # Asia-Pacific
    "BABA",   # Alibaba (China)
    "JD",     # JD.com (China)
    "PDD",    # PinDuoDuo (China)
    "BIDU",   # Baidu (China)
    "NIO",    # Nio EV (China)
    "XPEV",   # XPeng EV (China)
    "LI",     # Li Auto (China)
    "SE",     # Sea Limited (Singapore)
    "GRAB",   # Grab Holdings (Singapore)
    "SHOP",   # ... actually Canadian, listed on NYSE/TSX
    "TM",     # Toyota (Japan)
    "SONY",   # Sony (Japan)
    "HMC",    # Honda (Japan)
    "SNY",    # Sanofi (France/ADR)
    "SAP",    # SAP (Germany)
    "ASML",   # ASML (Netherlands)
    "NVO",    # Novo Nordisk (Denmark)
    "AZN",    # AstraZeneca (UK)
    "GSK",    # GSK (UK)
    "BP",     # BP (UK)
    "SHEL",   # Shell (UK)
    "RIO",    # Rio Tinto (Australia)
    "BHP",    # BHP Group (Australia)
    "VALE",   # Vale (Brazil)
    "PBR",    # Petrobras (Brazil)
    "ITUB",   # Itau Unibanco (Brazil)
    "BBD",    # Banco Bradesco (Brazil)
    "WIT",    # Wipro (India)
    "INFY",   # Infosys (India)
    "HDB",    # HDFC Bank (India)
    "IBN",    # ICICI Bank (India)
    # Europe
    "LVMH",   # LVMH (France) - actually not ADR but OTC
    "UL",     # Unilever (UK/Netherlands)
    "BTI",    # British American Tobacco (UK)
    "DEO",    # Diageo (UK)
    "BCS",    # Barclays (UK)
    "ING",    # ING Group (Netherlands)
    "DB",     # Deutsche Bank (Germany)
    "EADSY",  # Airbus (France/Germany/Spain)
    "SIE",    # Siemens (Germany) - Frankfurt listed
    "ABBNY",  # ABB (Switzerland)
    "NESN",   # Nestle (Switzerland)
    "RHHBY",  # Roche (Switzerland)
    "NVZMY",  # Novartis (Switzerland)
    # Americas
    "AMXL",   # America Movil (Mexico)
    "FEMSA",  # Fomento Economico (Mexico)
    "MFG",    # Mizuho Financial (Japan)
    "MUFG",   # Mitsubishi UFJ (Japan)
    "SAN",    # Banco Santander (Spain)
    "BBVA",   # BBVA (Spain)
    "ENI",    # ENI (Italy)
    "ENEL",   # Enel (Italy)
    # Telecom ADRs
    "ORAN",   # Orange (France)
    "VIV",    # Vivendi / Telefonica Brasil
    "TEF",    # Telefonica (Spain)
    "PHI",    # PLDT (Philippines)
    "SKM",    # SK Telecom (South Korea)
    "KT",     # KT Corp (South Korea)
]


def get_adr_tickers() -> list[str]:
    """Return a curated list of major ADR ticker symbols."""
    return sorted(set(_ADRS))


# ── Cryptocurrency ────────────────────────────────────────────────────────────
# Yahoo Finance format for crypto: BASE-USD (e.g. BTC-USD).
# Note: crypto trades 24/7, candlestick patterns apply but volatility is much
# higher — ATR-based targets will naturally be wider.

_CRYPTO: list[str] = [
    "BTC-USD",    # Bitcoin
    "ETH-USD",    # Ethereum
    "BNB-USD",    # BNB Chain
    "XRP-USD",    # Ripple
    "SOL-USD",    # Solana
    "ADA-USD",    # Cardano
    "AVAX-USD",   # Avalanche
    "DOGE-USD",   # Dogecoin
    "DOT-USD",    # Polkadot
    "MATIC-USD",  # Polygon
    "SHIB-USD",   # Shiba Inu
    "LTC-USD",    # Litecoin
    "UNI-USD",    # Uniswap
    "LINK-USD",   # Chainlink
    "XLM-USD",    # Stellar
    "ATOM-USD",   # Cosmos
    "XMR-USD",    # Monero
    "BCH-USD",    # Bitcoin Cash
    "ALGO-USD",   # Algorand
    "ICP-USD",    # Internet Computer
    "FIL-USD",    # Filecoin
    "VET-USD",    # VeChain
    "SAND-USD",   # The Sandbox
    "MANA-USD",   # Decentraland
    "APE-USD",    # ApeCoin
]


def get_crypto_tickers() -> list[str]:
    """Return a curated list of major cryptocurrency tickers (yfinance format)."""
    return sorted(_CRYPTO)


# ── Universe dispatcher ───────────────────────────────────────────────────────

#: Valid universe names accepted by get_tickers_for_universe()
UNIVERSE_NAMES: tuple[str, ...] = (
    "sp500", "nasdaq100", "dow30", "etf", "mutual_fund",
    "russell2000", "adr", "crypto", "all",
)


def get_tickers_for_universe(universe: str) -> list[str]:
    """
    Return a deduplicated, sorted ticker list for the requested universe.

    Parameters
    ----------
    universe:
        One of sp500, nasdaq100, dow30, etf, mutual_fund,
        russell2000, adr, crypto, or all.

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
    if universe == "russell2000":
        return get_russell2000_tickers()
    if universe == "adr":
        return get_adr_tickers()
    if universe == "crypto":
        return get_crypto_tickers()
    if universe == "all":
        combined = (
            get_sp500_tickers()
            + get_nasdaq100_tickers()
            + get_dow30_tickers()
            + get_etf_tickers()
            + get_mutual_fund_tickers()
            + get_russell2000_tickers()
            + get_adr_tickers()
            + get_crypto_tickers()
        )
        return sorted(set(combined))
    raise ValueError(
        f"Unknown universe {universe!r}. "
        f"Valid options: {', '.join(UNIVERSE_NAMES)}"
    )
