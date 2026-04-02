"""
Candlestick and structural pattern detection.

Each detector receives the full indicator-enriched DataFrame and returns a
``PatternMatch`` (or ``None`` if the pattern is absent).  Detectors are
stateless and composable.

Patterns implemented
--------------------
Bullish
    bullish_engulfing, hammer, morning_star_approx,
    rsi_oversold_bounce, macd_bullish_cross, golden_cross, bb_squeeze_breakout_up

Bearish
    bearish_engulfing, shooting_star, evening_star_approx,
    rsi_overbought_reversal, macd_bearish_cross, death_cross, bb_squeeze_breakout_down

Neutral
    inside_bar, doji, consolidation_range
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from bull.models.signal import PatternMatch


# ─────────────────────────────── utilities ──────────────────────────────────


def _last(df: pd.DataFrame, col: str, n: int = 0) -> float:
    return float(df[col].iloc[-(1 + n)])


def _body(df: pd.DataFrame, n: int = 0) -> float:
    return abs(_last(df, "Close", n) - _last(df, "Open", n))


def _full_range(df: pd.DataFrame, n: int = 0) -> float:
    return _last(df, "High", n) - _last(df, "Low", n)


def _is_green(df: pd.DataFrame, n: int = 0) -> bool:
    return _last(df, "Close", n) > _last(df, "Open", n)


def _is_red(df: pd.DataFrame, n: int = 0) -> bool:
    return _last(df, "Close", n) < _last(df, "Open", n)


def _red_run(df: pd.DataFrame, length: int) -> int:
    """Count consecutive red candles ending at second-to-last row."""
    count = 0
    for i in range(1, min(length + 1, len(df))):
        if _is_red(df, i):
            count += 1
        else:
            break
    return count


def _pct(df: pd.DataFrame) -> float:
    """Body size of last candle as % of open."""
    o = _last(df, "Open")
    if o == 0:
        return 0.0
    return (_body(df) / o) * 100.0


# ─────────────────────────── bullish patterns ───────────────────────────────


def bullish_engulfing(df: pd.DataFrame) -> PatternMatch | None:
    """
    Classic bullish engulfing with ≥3 prior red days.

    Conditions
    ----------
    - Last candle is green and opens below prev close, closes above prev open
    - ≥3 of the preceding 4 candles are red
    - Body ≥ 0.8 % of open
    - Volume ratio ≥ 1.10
    """
    if len(df) < 6:
        return None

    prev = 1  # index offset for second-to-last

    last_green = _is_green(df, 0)
    engulfs = (
        _last(df, "Open") < _last(df, "Close", prev)
        and _last(df, "Close") > _last(df, "Open", prev)
    )

    if not (last_green and engulfs):
        return None

    red_count = sum(1 for i in range(1, 5) if _is_red(df, i))
    if red_count < 3:
        return None

    body_pct = _pct(df)
    vol_ratio = _last(df, "Volume_ratio")

    if body_pct < 0.8 or vol_ratio < 1.10:
        return None

    strength = min(1.0, (body_pct / 3.0) * 0.5 + ((vol_ratio - 1.0) / 0.5) * 0.5)
    return PatternMatch(
        name="Bullish Engulfing",
        strength=round(strength, 3),
        description=(
            f"Green candle engulfs prior red after {red_count} down-days "
            f"(body {body_pct:.1f}%, vol {vol_ratio:.2f}×)"
        ),
    )


def hammer(df: pd.DataFrame) -> PatternMatch | None:
    """
    Hammer: small body at top, long lower wick ≥ 2× body, tiny upper wick.
    Confirms potential bottom after a downtrend.
    """
    if len(df) < 3:
        return None
    if not (_is_red(df, 1) and _is_red(df, 2)):
        return None  # need prior down-trend

    body = _body(df)
    full = _full_range(df)
    if full == 0 or body == 0:
        return None

    lower_wick = min(_last(df, "Open"), _last(df, "Close")) - _last(df, "Low")
    upper_wick = _last(df, "High") - max(_last(df, "Open"), _last(df, "Close"))

    if lower_wick < 2 * body:
        return None
    if upper_wick > body:
        return None

    strength = min(1.0, lower_wick / (body * 3))
    return PatternMatch(
        name="Hammer",
        strength=round(strength, 3),
        description=(
            f"Hammer candle after downtrend — lower wick {lower_wick:.2f} "
            f"is {lower_wick / body:.1f}× the body"
        ),
    )


def rsi_oversold_bounce(df: pd.DataFrame) -> PatternMatch | None:
    """RSI crossed above 30 in the last 2 days (recovery from oversold)."""
    if len(df) < 3 or "RSI_14" not in df.columns:
        return None
    rsi_now = _last(df, "RSI_14", 0)
    rsi_prev = _last(df, "RSI_14", 1)
    if rsi_prev < 35 and rsi_now > rsi_prev and rsi_now < 55:
        strength = min(1.0, (55 - rsi_now) / 20)
        return PatternMatch(
            name="RSI Oversold Bounce",
            strength=round(strength, 3),
            description=f"RSI recovering from oversold: {rsi_prev:.1f} → {rsi_now:.1f}",
        )
    return None


def macd_bullish_cross(df: pd.DataFrame) -> PatternMatch | None:
    """MACD line crossed above signal line in the last 2 candles."""
    if len(df) < 3 or "MACD_line" not in df.columns:
        return None
    crossed = _last(df, "MACD_line", 1) < _last(df, "MACD_signal", 1) and \
              _last(df, "MACD_line", 0) > _last(df, "MACD_signal", 0)
    if not crossed:
        return None
    hist = _last(df, "MACD_hist")
    strength = min(1.0, abs(hist) / 0.5)
    return PatternMatch(
        name="MACD Bullish Cross",
        strength=round(strength, 3),
        description=f"MACD crossed above signal line (hist {hist:.4f})",
    )


def golden_cross(df: pd.DataFrame) -> PatternMatch | None:
    """SMA_50 crossed above SMA_200 in the last 3 days."""
    if len(df) < 4 or "SMA_50" not in df.columns or "SMA_200" not in df.columns:
        return None
    for i in range(1, 4):
        below = _last(df, "SMA_50", i) < _last(df, "SMA_200", i)
        above = _last(df, "SMA_50", 0) > _last(df, "SMA_200", 0)
        if below and above:
            return PatternMatch(
                name="Golden Cross",
                strength=0.85,
                description="SMA-50 crossed above SMA-200 (golden cross)",
            )
    return None


def bb_breakout_up(df: pd.DataFrame) -> PatternMatch | None:
    """Close broke above the upper Bollinger Band today."""
    if "BB_upper" not in df.columns:
        return None
    if _last(df, "Close") > _last(df, "BB_upper"):
        excess = (_last(df, "Close") - _last(df, "BB_upper")) / _last(df, "BB_upper") * 100
        return PatternMatch(
            name="BB Breakout Up",
            strength=min(1.0, 0.5 + excess / 5),
            description=f"Close {excess:.2f}% above upper Bollinger Band",
        )
    return None


# ─────────────────────────── bearish patterns ───────────────────────────────


def bearish_engulfing(df: pd.DataFrame) -> PatternMatch | None:
    """Bearish engulfing with ≥3 prior green days."""
    if len(df) < 6:
        return None
    prev = 1
    last_red = _is_red(df, 0)
    engulfs = (
        _last(df, "Open") > _last(df, "Close", prev)
        and _last(df, "Close") < _last(df, "Open", prev)
    )
    if not (last_red and engulfs):
        return None
    green_count = sum(1 for i in range(1, 5) if _is_green(df, i))
    if green_count < 3:
        return None
    body_pct = _pct(df)
    vol_ratio = _last(df, "Volume_ratio")
    if body_pct < 0.8 or vol_ratio < 1.10:
        return None
    strength = min(1.0, (body_pct / 3.0) * 0.5 + ((vol_ratio - 1.0) / 0.5) * 0.5)
    return PatternMatch(
        name="Bearish Engulfing",
        strength=round(strength, 3),
        description=(
            f"Red candle engulfs prior green after {green_count} up-days "
            f"(body {body_pct:.1f}%, vol {vol_ratio:.2f}×)"
        ),
    )


def shooting_star(df: pd.DataFrame) -> PatternMatch | None:
    """Shooting star: small body at bottom, long upper wick ≥ 2× body."""
    if len(df) < 3:
        return None
    if not (_is_green(df, 1) and _is_green(df, 2)):
        return None
    body = _body(df)
    if body == 0:
        return None
    upper_wick = _last(df, "High") - max(_last(df, "Open"), _last(df, "Close"))
    lower_wick = min(_last(df, "Open"), _last(df, "Close")) - _last(df, "Low")
    if upper_wick < 2 * body or lower_wick > body:
        return None
    strength = min(1.0, upper_wick / (body * 3))
    return PatternMatch(
        name="Shooting Star",
        strength=round(strength, 3),
        description=(
            f"Shooting star after uptrend — upper wick {upper_wick:.2f} "
            f"is {upper_wick / body:.1f}× the body"
        ),
    )


def rsi_overbought_reversal(df: pd.DataFrame) -> PatternMatch | None:
    """RSI crossed below 70 in the last 2 days (fading from overbought)."""
    if "RSI_14" not in df.columns:
        return None
    rsi_now = _last(df, "RSI_14", 0)
    rsi_prev = _last(df, "RSI_14", 1)
    if rsi_prev > 65 and rsi_now < rsi_prev and rsi_now > 50:
        strength = min(1.0, (rsi_prev - 50) / 30)
        return PatternMatch(
            name="RSI Overbought Reversal",
            strength=round(strength, 3),
            description=f"RSI fading from overbought: {rsi_prev:.1f} → {rsi_now:.1f}",
        )
    return None


def macd_bearish_cross(df: pd.DataFrame) -> PatternMatch | None:
    """MACD line crossed below signal line in the last 2 candles."""
    if "MACD_line" not in df.columns:
        return None
    crossed = _last(df, "MACD_line", 1) > _last(df, "MACD_signal", 1) and \
              _last(df, "MACD_line", 0) < _last(df, "MACD_signal", 0)
    if not crossed:
        return None
    hist = _last(df, "MACD_hist")
    strength = min(1.0, abs(hist) / 0.5)
    return PatternMatch(
        name="MACD Bearish Cross",
        strength=round(strength, 3),
        description=f"MACD crossed below signal line (hist {hist:.4f})",
    )


def death_cross(df: pd.DataFrame) -> PatternMatch | None:
    """SMA_50 crossed below SMA_200 in the last 3 days."""
    if "SMA_50" not in df.columns or "SMA_200" not in df.columns:
        return None
    for i in range(1, 4):
        above = _last(df, "SMA_50", i) > _last(df, "SMA_200", i)
        below = _last(df, "SMA_50", 0) < _last(df, "SMA_200", 0)
        if above and below:
            return PatternMatch(
                name="Death Cross",
                strength=0.85,
                description="SMA-50 crossed below SMA-200 (death cross)",
            )
    return None


def bb_breakout_down(df: pd.DataFrame) -> PatternMatch | None:
    """Close broke below the lower Bollinger Band today."""
    if "BB_lower" not in df.columns:
        return None
    if _last(df, "Close") < _last(df, "BB_lower"):
        excess = (_last(df, "BB_lower") - _last(df, "Close")) / _last(df, "BB_lower") * 100
        return PatternMatch(
            name="BB Breakdown",
            strength=min(1.0, 0.5 + excess / 5),
            description=f"Close {excess:.2f}% below lower Bollinger Band",
        )
    return None


# ─────────────────────────── neutral patterns ───────────────────────────────


def inside_bar(df: pd.DataFrame) -> PatternMatch | None:
    """Inside bar: entire range of today inside prior candle's range."""
    if len(df) < 2:
        return None
    if (_last(df, "High") < _last(df, "High", 1)
            and _last(df, "Low") > _last(df, "Low", 1)):
        return PatternMatch(
            name="Inside Bar",
            strength=0.5,
            description="Today's range is fully contained within yesterday's — consolidation",
        )
    return None


def doji(df: pd.DataFrame) -> PatternMatch | None:
    """Doji: body ≤ 10% of full range, indicating indecision."""
    full = _full_range(df)
    if full == 0:
        return None
    ratio = _body(df) / full
    if ratio <= 0.10:
        return PatternMatch(
            name="Doji",
            strength=round(1.0 - ratio / 0.10, 3),
            description=f"Doji candle — body is only {ratio * 100:.1f}% of range",
        )
    return None


def consolidation_range(df: pd.DataFrame) -> PatternMatch | None:
    """
    Consolidation: last 5-day ATR is ≤ 50% of the 20-day ATR,
    suggesting a tight, low-volatility band.
    """
    if "ATR_14" not in df.columns or len(df) < 25:
        return None
    recent_atr = float(df["ATR_14"].iloc[-5:].mean())
    long_atr = float(df["ATR_14"].iloc[-20:].mean())
    if long_atr == 0:
        return None
    ratio = recent_atr / long_atr
    if ratio <= 0.50:
        return PatternMatch(
            name="Consolidation Range",
            strength=round(1.0 - ratio, 3),
            description=(
                f"5-day ATR ({recent_atr:.2f}) is {ratio * 100:.0f}% of "
                f"20-day ATR ({long_atr:.2f}) — tight compression"
            ),
        )
    return None
