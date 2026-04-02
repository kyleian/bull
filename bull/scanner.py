"""
Core scanning loop.

Runs one or more scan modes across all S&P 500 tickers using a thread-pool
for concurrency.  Returns a ``ScanResult`` per mode.
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from bull.analysis.bearish import scan_bearish
from bull.analysis.bullish import scan_bullish
from bull.analysis.neutral import scan_neutral
from bull.config import ScanMode, settings
from bull.data.market import fetch_market_data
from bull.data.tickers import get_sp500_tickers
from bull.exceptions import MarketDataError
from bull.models.signal import ScanResult, Signal

log = logging.getLogger(__name__)

_MODE_FN = {
    ScanMode.BULLISH: scan_bullish,
    ScanMode.BEARISH: scan_bearish,
    ScanMode.NEUTRAL: scan_neutral,
}


def run_scan(
    mode: ScanMode,
    tickers: list[str] | None = None,
    concurrency: int | None = None,
) -> ScanResult:
    """
    Scan all S&P 500 tickers (or a supplied subset) for the given mode.

    Parameters
    ----------
    mode:
        One of ``bullish``, ``bearish``, ``neutral``, or ``all``.
        If ``all``, three separate ``ScanResult`` objects are returned
        by ``run_all_modes`` instead.
    tickers:
        Override the default S&P 500 ticker list (useful for testing).
    concurrency:
        Thread count.  Defaults to ``settings.concurrency``.

    Returns
    -------
    ScanResult
    """
    if mode == ScanMode.ALL:
        raise ValueError("Use run_all_modes() for ScanMode.ALL")

    scan_fn = _MODE_FN[mode]
    ticker_list = tickers or get_sp500_tickers()
    workers = concurrency or settings.concurrency

    errors: dict[str, str] = {}

    log.info("Starting %s scan over %d tickers (concurrency=%d)", mode, len(ticker_list), workers)

    def _process(ticker: str) -> Signal | None:
        try:
            data = fetch_market_data(ticker)
            return scan_fn(data)
        except MarketDataError as exc:
            errors[ticker] = str(exc)
            log.debug("[%s] data error: %s", ticker, exc)
            return None
        except Exception as exc:
            errors[ticker] = f"unexpected: {exc}"
            log.warning("[%s] unexpected error: %s", ticker, exc)
            return None

    # Collect ALL candidates (above and below threshold) so we can always
    # surface at least min_results picks even on a quiet day.
    all_candidates: list[Signal] = []

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_process, t): t for t in ticker_list}
        done = 0
        for future in as_completed(futures):
            result = future.result()
            if result is not None:
                all_candidates.append(result)
            done += 1
            if done % 50 == 0:
                log.info("Progress: %d/%d scanned, %d candidates so far", done, len(ticker_list), len(all_candidates))

    # Sort best-first, then split into confirmed signals vs fill picks
    all_candidates.sort(key=lambda s: s.score, reverse=True)
    confirmed = [s for s in all_candidates if s.above_threshold]
    picks = [s for s in all_candidates if not s.above_threshold]

    min_r = settings.min_results
    # Always include all confirmed; pad with best picks to reach min_results
    shortfall = max(0, min_r - len(confirmed))
    surfaced = confirmed + picks[:shortfall]

    signals_count = len(confirmed)
    log.info(
        "%s scan complete: %d confirmed signal(s), %d watch pick(s) surfaced, %d errors",
        mode, signals_count, len(surfaced) - signals_count, len(errors),
    )
    return ScanResult(
        mode=str(mode),
        total_scanned=len(ticker_list),
        total_signals=signals_count,
        signals=surfaced,
        errors=errors,
    )


def run_all_modes(
    tickers: list[str] | None = None,
    concurrency: int | None = None,
) -> list[ScanResult]:
    """
    Run bullish, bearish, and neutral scans and return a list of results.
    """
    return [
        run_scan(ScanMode.BULLISH, tickers, concurrency),
        run_scan(ScanMode.BEARISH, tickers, concurrency),
        run_scan(ScanMode.NEUTRAL, tickers, concurrency),
    ]
