"""
Bullish mode scanner.

Runs all bullish pattern detectors against indicator-enriched price data
and assembles a ``Signal`` when enough evidence accumulates.

Detection stack
---------------
bullish_engulfing   — Chris' core pattern (highest weight)
hammer              — hammer candle after downtrend
rsi_oversold_bounce — RSI recovering from < 35
macd_bullish_cross  — MACD line crossing above signal
golden_cross        — SMA-50 crossing above SMA-200
bb_breakout_up      — close above upper Bollinger Band

A signal is emitted when the composite score ≥ ``settings.min_signal_score``.
"""

from __future__ import annotations

import logging

from bull.analysis._shared import build_signal, extract_indicators
from bull.analysis import patterns as P
from bull.analysis.technical import add_all
from bull.config import settings
from bull.data.market import MarketData
from bull.models.signal import PatternMatch, Signal
from bull.scoring import score_patterns

log = logging.getLogger(__name__)

# Ordered list of (detector_fn, weight) — higher weight = more impact on score
_DETECTORS: list[tuple] = [
    (P.bullish_engulfing,   3.0),
    (P.hammer,              2.0),
    (P.rsi_oversold_bounce, 2.0),
    (P.macd_bullish_cross,  1.5),
    (P.golden_cross,        2.5),
    (P.bb_breakout_up,      1.5),
]


def scan_bullish(data: MarketData) -> Signal | None:
    """
    Analyse *data* for bullish setups.

    Returns a ``Signal`` when the composite score meets the threshold,
    otherwise returns ``None``.  Never raises — errors are logged and
    suppressed so the scanner loop can continue without interruption.
    """
    ticker = data.ticker
    try:
        df = add_all(data.df)
        if len(df) < settings.min_history_rows:
            log.debug("[%s] insufficient rows after indicator calculation", ticker)
            return None

        matched: list[PatternMatch] = []
        for detector, _weight in _DETECTORS:
            result = detector(df)
            if result is not None:
                matched.append(result)

        if not matched:
            return None

        score = score_patterns(matched, _DETECTORS)
        if score < settings.min_signal_score:
            log.debug("[%s] score %.2f below threshold", ticker, score)
            return None

        indicators = extract_indicators(df)
        rationale = _build_rationale(data, indicators, matched)
        log.info("[%s] bullish signal (score %.2f)", ticker, score)

        return build_signal(
            ticker=ticker,
            company_name=data.company_name,
            sector=data.sector,
            description=data.description,
            mode="bullish",
            df=df,
            indicators=indicators,
            patterns=matched,
            score=score,
            rationale=rationale,
            direction="up",
        )

    except Exception as exc:
        log.warning("[%s] bullish scan error (skipped): %s", ticker, exc)
        return None


def _build_rationale(data: MarketData, indicators: object, matched: list[PatternMatch]) -> list[str]:
    lines: list[str] = [f"Pattern: {p.name} (strength {p.strength:.2f})" for p in matched]
    ind = indicators  # type: ignore[attr-defined]
    if not (ind.rsi_14 != ind.rsi_14):  # isnan check
        lines.append(f"RSI-14: {ind.rsi_14:.1f} — {'oversold territory' if ind.rsi_14 < 40 else 'neutral'}")
    if not (ind.distance_from_sma50 != ind.distance_from_sma50):
        lines.append(f"Distance from SMA-50: {ind.distance_from_sma50:+.1f}%")
    if not (ind.macd_hist != ind.macd_hist):
        lines.append(f"MACD histogram: {ind.macd_hist:+.4f} ({'positive momentum' if ind.macd_hist > 0 else 'negative momentum'})")
    return lines
