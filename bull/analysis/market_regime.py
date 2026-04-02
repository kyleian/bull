"""
Market regime detector.

Classifies the current broad-market environment so individual signals can be
weighted accordingly.  For example, bullish patterns in a confirmed bear
market should be labelled as counter-trend trades.

Regime classification
---------------------
bull        SPY above SMA-200, VIX < 20, positive momentum
recovery    SPY below SMA-200 but rising, VIX declining
volatile    VIX > 25, large daily swings
bear        SPY below SMA-200, VIX elevated, negative momentum
sideways    SPY near SMA-200, low volatility
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import lru_cache
from datetime import date, timedelta

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)

# Regime thresholds
_VIX_CALM = 18.0
_VIX_ELEVATED = 25.0
_VIX_FEAR = 35.0
_NEAR_SMA200_PCT = 3.0  # within 3% counts as "near"


@dataclass
class MarketRegime:
    """Broad-market context snapshot."""

    regime: str                  # "bull" | "bear" | "volatile" | "recovery" | "sideways"
    spy_price: float = 0.0
    spy_vs_sma200_pct: float = 0.0   # % above/below SMA-200
    spy_vs_sma50_pct: float = 0.0
    vix: float = 0.0
    market_trend: str = "neutral"    # "up" | "down" | "neutral"
    breadth_note: str = ""           # human-readable market breadth comment
    summary: str = ""                # one-line regime description for reports


def detect() -> MarketRegime:
    """
    Detect current market regime from SPY + VIX data.
    Cached for 1 hour so repeated calls within a scan session are free.
    """
    return _detect_cached(date.today().isoformat())


@lru_cache(maxsize=4)
def _detect_cached(date_key: str) -> MarketRegime:  # noqa: ARG001  (date_key is the cache key)
    """Internal cached implementation — refreshes once per calendar day."""
    import yfinance as yf  # lazy import to keep startup fast

    spy_price = 0.0
    spy_sma200 = 0.0
    spy_sma50 = 0.0
    vix = 0.0

    try:
        spy_df = yf.Ticker("SPY").history(period="300d")
        if not spy_df.empty:
            close = spy_df["Close"]
            spy_price = float(close.iloc[-1])
            spy_sma200 = float(close.rolling(200).mean().iloc[-1])
            spy_sma50 = float(close.rolling(50).mean().iloc[-1])
    except Exception as exc:
        log.warning("Could not fetch SPY for regime detection: %s", exc)

    try:
        vix_df = yf.Ticker("^VIX").history(period="5d")
        if not vix_df.empty:
            vix = float(vix_df["Close"].iloc[-1])
    except Exception as exc:
        log.warning("Could not fetch VIX: %s", exc)

    return _classify(spy_price, spy_sma200, spy_sma50, vix)


def _classify(spy: float, sma200: float, sma50: float, vix: float) -> MarketRegime:
    """Pure classification function (easy to unit-test)."""

    vs200 = ((spy - sma200) / sma200 * 100) if sma200 > 0 else 0.0
    vs50 = ((spy - sma50) / sma50 * 100) if sma50 > 0 else 0.0

    above_200 = vs200 > 0
    near_200 = abs(vs200) <= _NEAR_SMA200_PCT

    if vix >= _VIX_FEAR:
        regime = "volatile"
        summary = f"VOLATILE MARKET: VIX={vix:.1f} (extreme fear). High risk environment."
    elif not above_200 and vix >= _VIX_ELEVATED:
        regime = "bear"
        summary = (
            f"BEAR MARKET: SPY {vs200:.1f}% below 200-SMA, VIX={vix:.1f}. "
            "Favour shorts / defensive positions."
        )
    elif not above_200 and vs50 > 0:
        regime = "recovery"
        summary = (
            f"RECOVERY: SPY below 200-SMA ({vs200:.1f}%) but above 50-SMA. "
            "Early bounce — monitor closely."
        )
    elif near_200:
        regime = "sideways"
        summary = (
            f"SIDEWAYS: SPY near 200-SMA ({vs200:+.1f}%). "
            "No clear directional bias — wait for confirmation."
        )
    elif above_200 and vix <= _VIX_CALM:
        regime = "bull"
        summary = (
            f"BULL MARKET: SPY {vs200:.1f}% above 200-SMA, VIX={vix:.1f} (calm). "
            "Favourable conditions for longs."
        )
    elif above_200:
        regime = "bull"
        summary = (
            f"BULL MARKET (elevated VIX): SPY {vs200:.1f}% above 200-SMA, "
            f"VIX={vix:.1f}. Proceed with caution."
        )
    else:
        regime = "bear"
        summary = f"BEAR MARKET: SPY {vs200:.1f}% below 200-SMA. Caution advised."

    breadth = _breadth_note(above_200, vs50, vix)
    trend = "up" if vs50 > 1.5 else "down" if vs50 < -1.5 else "neutral"

    return MarketRegime(
        regime=regime,
        spy_price=spy,
        spy_vs_sma200_pct=round(vs200, 2),
        spy_vs_sma50_pct=round(vs50, 2),
        vix=round(vix, 1),
        market_trend=trend,
        breadth_note=breadth,
        summary=summary,
    )


def _breadth_note(above_200: bool, vs50: float, vix: float) -> str:
    parts: list[str] = []
    if above_200:
        parts.append("Broad market in uptrend")
    else:
        parts.append("Broad market in downtrend")
    if vix > _VIX_ELEVATED:
        parts.append(f"high volatility (VIX {vix:.0f})")
    elif vix < _VIX_CALM:
        parts.append(f"low volatility (VIX {vix:.0f})")
    if vs50 > 2:
        parts.append("short-term momentum positive")
    elif vs50 < -2:
        parts.append("short-term momentum negative")
    return "; ".join(parts)
