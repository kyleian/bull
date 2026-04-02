"""
Bearish mode scanner.

Detection stack
---------------
bearish_engulfing        — mirror of the bullish engulfing (highest weight)
shooting_star            — long upper wick after uptrend
rsi_overbought_reversal  — RSI fading from > 65
macd_bearish_cross       — MACD below signal line
death_cross              — SMA-50 crossing below SMA-200
bb_breakout_down         — close below lower Bollinger Band

Signals fire in the *bearish* direction — targets and stop-loss are inverted.
"""

from __future__ import annotations

import logging

from bull.analysis._shared import build_signal, extract_indicators
from bull.analysis import patterns as P
from bull.analysis.technical import add_all
from bull.config import settings
from bull.data.market import MarketData
from bull.models.signal import PatternMatch, Signal, SentimentData, MarketRegimeSnapshot
from bull.scoring import score_patterns

log = logging.getLogger(__name__)

_DETECTORS: list[tuple] = [
    (P.bearish_engulfing,          3.0),
    (P.shooting_star,              2.0),
    (P.rsi_overbought_reversal,    2.0),
    (P.macd_bearish_cross,         1.5),
    (P.death_cross,                2.5),
    (P.bb_breakout_down,           1.5),
]


def scan_bearish(data: MarketData) -> Signal | None:
    """
    Analyse *data* for bearish setups.

    Returns a ``Signal`` targeting the short/put side, otherwise ``None``.
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
            log.info("[%s] bearish signal (score %.2f)", ticker, score)
        else:
            log.debug("[%s] bearish candidate (score %.2f, below threshold)", ticker, score)

        indicators = extract_indicators(df)
        rationale = _build_rationale(data, indicators, matched)

        # -- Sentiment + market regime ----------------------------------------
        sentiment = SentimentData()
        regime_snap = MarketRegimeSnapshot()

        if settings.enable_sentiment:
            try:
                from bull.analysis import sentiment as SA
                sentiment = SA.analyse(ticker, tuple(data.news_headlines))
                if sentiment.catalyst_summary:
                    rationale.append(f"[NEWS] {sentiment.catalyst_summary}")
            except Exception as exc:
                log.debug("[%s] sentiment analysis failed (non-fatal): %s", ticker, exc)

        if settings.enable_market_regime:
            try:
                from bull.analysis import market_regime as MR
                regime = MR.detect()
                regime_snap = MarketRegimeSnapshot(
                    regime=regime.regime,
                    spy_vs_sma200_pct=regime.spy_vs_sma200_pct,
                    vix=regime.vix,
                    summary=regime.summary,
                )
                rationale.append(f"[MARKET] {regime.summary}")
                if regime.regime == "bull":
                    rationale.append("[CAUTION] Bearish signal in bull market — higher risk of being squeezed.")
            except Exception as exc:
                log.debug("[%s] regime detection failed (non-fatal): %s", ticker, exc)

        return build_signal(
            ticker=ticker,
            company_name=data.company_name,
            sector=data.sector,
            description=data.description,
            mode="bearish",
            df=df,
            indicators=indicators,
            patterns=matched,
            score=score,
            rationale=rationale,
            direction="down",
            above_threshold=above,
            sentiment=sentiment,
            regime=regime_snap,
        )

    except Exception as exc:
        log.warning("[%s] bearish scan error (skipped): %s", ticker, exc)
        return None


def _build_rationale(data: MarketData, indicators: object, matched: list[PatternMatch]) -> list[str]:
    lines: list[str] = [f"Pattern: {p.name} (strength {p.strength:.2f})" for p in matched]
    ind = indicators  # type: ignore[attr-defined]
    if not (ind.rsi_14 != ind.rsi_14):
        lines.append(f"RSI-14: {ind.rsi_14:.1f} — {'overbought territory' if ind.rsi_14 > 60 else 'neutral'}")
    if not (ind.distance_from_sma50 != ind.distance_from_sma50):
        lines.append(f"Distance from SMA-50: {ind.distance_from_sma50:+.1f}%")
    if not (ind.macd_hist != ind.macd_hist):
        lines.append(f"MACD histogram: {ind.macd_hist:+.4f} ({'negative momentum' if ind.macd_hist < 0 else 'positive momentum'})")
    return lines
