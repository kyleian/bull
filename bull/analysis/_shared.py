"""
Shared helpers used by all scanner modes.

Handles: indicator extraction, option date/strike generation, Signal assembly.
"""

from __future__ import annotations

import math
from datetime import date, timedelta

import numpy as np
import pandas as pd

from bull.models.signal import Indicators, PatternMatch, Signal, SentimentData, MarketRegimeSnapshot


def extract_indicators(df: pd.DataFrame) -> Indicators:
    """Pull the last row of indicator columns into an ``Indicators`` object."""

    def _g(col: str, default: float = float("nan")) -> float:
        if col in df.columns:
            val = df[col].iloc[-1]
            return float(val) if pd.notna(val) else default
        return default

    close = _g("Close")
    sma_50 = _g("SMA_50")
    sma_200 = _g("SMA_200")
    dist_50 = ((close - sma_50) / sma_50) * 100 if not math.isnan(sma_50) and sma_50 != 0 else float("nan")
    dist_200 = ((close - sma_200) / sma_200) * 100 if not math.isnan(sma_200) and sma_200 != 0 else float("nan")

    return Indicators(
        sma_20=_g("SMA_20"),
        sma_50=sma_50,
        sma_200=sma_200,
        rsi_14=_g("RSI_14"),
        macd_line=_g("MACD_line"),
        macd_signal=_g("MACD_signal"),
        macd_hist=_g("MACD_hist"),
        atr_14=_g("ATR_14"),
        bb_upper=_g("BB_upper"),
        bb_lower=_g("BB_lower"),
        bb_mid=_g("BB_mid"),
        volume_ratio=_g("Volume_ratio"),
        distance_from_sma50=dist_50,
        distance_from_sma200=dist_200,
    )


def _next_fridays(n: int = 2) -> list[str]:
    """Return the next *n* Fridays (7-14 days out) as ISO strings."""
    results: list[str] = []
    today = date.today()
    days_ahead = 1
    while len(results) < n and days_ahead <= 21:
        candidate = today + timedelta(days=days_ahead)
        if candidate.weekday() == 4 and 3 <= days_ahead <= 14:
            results.append(candidate.isoformat())
        days_ahead += 1
    return results


def _suggest_strikes(price: float, target: float) -> dict[str, float]:
    inc = 2.5 if price < 50 else (5.0 if price < 200 else 10.0)
    atm = round(price / inc) * inc
    return {"ITM": round(atm - inc, 2), "ATM": round(atm, 2), "OTM": round(atm + inc, 2)}


def _atr_targets(
    entry: float, atr: float, direction: str = "up"
) -> tuple[float, float, float]:
    """Return (target_quick, target_extended, stop_loss)."""
    if direction == "up":
        tq = entry + 1.5 * atr
        te = entry + 2.5 * atr
        sl = entry - 1.5 * atr
    else:
        tq = entry - 1.5 * atr
        te = entry - 2.5 * atr
        sl = entry + 1.5 * atr
    return round(tq, 2), round(te, 2), round(sl, 2)


def build_signal(
    *,
    ticker: str,
    company_name: str,
    sector: str,
    description: str,
    mode: str,
    df: pd.DataFrame,
    indicators: Indicators,
    patterns: list[PatternMatch],
    score: float,
    rationale: list[str],
    direction: str = "up",
    above_threshold: bool = True,
    sentiment: SentimentData | None = None,
    regime: MarketRegimeSnapshot | None = None,
) -> Signal:
    close = float(df["Close"].iloc[-1])
    atr = indicators.atr_14 if not math.isnan(indicators.atr_14) else close * 0.02
    tq, te, sl = _atr_targets(close, atr, direction)
    rr = abs(tq - close) / abs(close - sl) if abs(close - sl) > 0 else 0.0
    body = abs(float(df["Close"].iloc[-1]) - float(df["Open"].iloc[-1]))
    open_price = float(df["Open"].iloc[-1])
    body_pct = (body / open_price * 100) if open_price else 0.0
    red_days = sum(1 for i in range(1, 5) if float(df["Close"].iloc[-(i + 1)]) < float(df["Open"].iloc[-(i + 1)]))

    return Signal(
        ticker=ticker,
        company_name=company_name,
        sector=sector,
        description=description,
        mode=mode,  # type: ignore[arg-type]
        signal_date=date.today(),
        current_price=round(close, 2),
        entry_price=round(close, 2),
        target_quick=tq,
        target_extended=te,
        stop_loss=sl,
        indicators=indicators,
        patterns=patterns,
        score=round(score, 2),
        stars=max(1, min(5, round(score / 2))),
        above_threshold=above_threshold,
        rationale=rationale,
        risk_reward=round(rr, 2),
        sentiment=sentiment or SentimentData(),
        regime=regime or MarketRegimeSnapshot(),
        option_expirations=_next_fridays(),
        suggested_strikes=_suggest_strikes(close, tq),
        expected_option_profit_pct=round(((tq - close) / close * 100) * 2.5, 1),
        weekly_resistance=round(float(df["High"].tail(20).max()), 2),
        body_size_pct=round(body_pct, 2),
        red_days_prior=red_days,
    )
