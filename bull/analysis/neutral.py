"""
Neutral / consolidation mode scanner.

Looks for range-bound tickers that may be coiling for a breakout.

Detection stack
---------------
inside_bar            — today's range inside yesterday's
doji                  — high indecision candle
consolidation_range   — 5-day ATR ≤ 50% of 20-day ATR (tight squeeze)

Neutral signals are informational — targets use the upper Bollinger Band as
a breakout target and the lower band as the stop-loss.
"""

from __future__ import annotations

import logging
import math

from bull.analysis._shared import extract_indicators
from bull.analysis import patterns as P
from bull.analysis.technical import add_all
from bull.config import settings
from bull.data.market import MarketData
from bull.models.signal import PatternMatch, Signal
from bull.scoring import score_patterns
from bull.analysis._shared import build_signal

log = logging.getLogger(__name__)

_DETECTORS: list[tuple] = [
    (P.inside_bar,           2.0),
    (P.doji,                 1.5),
    (P.consolidation_range,  3.0),
]


def scan_neutral(data: MarketData) -> Signal | None:
    """
    Analyse *data* for neutral / consolidation setups.

    Returns a ``Signal`` in "neutral" mode, or ``None``.
    """
    ticker = data.ticker
    try:
        df = add_all(data.df)
        if len(df) < settings.min_history_rows:
            return None

        matched: list[PatternMatch] = []
        for detector, _weight in _DETECTORS:
            result = detector(df)
            if result is not None:
                matched.append(result)

        if not matched:
            return None

        score = score_patterns(matched, _DETECTORS)
        above = score >= settings.min_signal_score
        if above:
            log.info("[%s] neutral signal (score %.2f)", ticker, score)
        else:
            log.debug("[%s] neutral candidate (score %.2f)", ticker, score)

        indicators = extract_indicators(df)
        rationale = _build_rationale(indicators, matched)

        return build_signal(
            ticker=ticker,
            company_name=data.company_name,
            sector=data.sector,
            description=data.description,
            mode="neutral",
            df=df,
            indicators=indicators,
            patterns=matched,
            score=score,
            rationale=rationale,
            direction="up",
            above_threshold=above,
        )

    except Exception as exc:
        log.warning("[%s] neutral scan error (skipped): %s", ticker, exc)
        return None


def _build_rationale(indicators: object, matched: list[PatternMatch]) -> list[str]:
    ind = indicators  # type: ignore[attr-defined]
    lines = [f"Pattern: {p.name} — {p.description}" for p in matched]
    if not math.isnan(ind.rsi_14):
        lines.append(f"RSI-14: {ind.rsi_14:.1f} (neutral zone = 40–60)")
    if not math.isnan(ind.distance_from_sma50):
        lines.append(f"Distance from SMA-50: {ind.distance_from_sma50:+.1f}%")
    lines.append("Watch for volume expansion to confirm breakout direction.")
    return lines
