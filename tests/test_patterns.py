"""Tests for bull.analysis.patterns"""

from __future__ import annotations

import pytest
import pandas as pd

from bull.analysis.technical import add_all
from bull.analysis.patterns import (
    bullish_engulfing,
    bearish_engulfing,
    hammer,
    shooting_star,
    rsi_oversold_bounce,
    rsi_overbought_reversal,
    macd_bullish_cross,
    macd_bearish_cross,
    inside_bar,
    doji,
)


class TestBullishEngulfing:
    def test_detects_pattern(self, bullish_engulfing_df: pd.DataFrame) -> None:
        df = add_all(bullish_engulfing_df)
        result = bullish_engulfing(df)
        assert result is not None
        assert result.name == "Bullish Engulfing"
        assert 0 < result.strength <= 1.0

    def test_no_signal_on_flat(self, flat_df: pd.DataFrame) -> None:
        df = add_all(flat_df)
        assert bullish_engulfing(df) is None

    def test_no_signal_on_bearish_engulfing(self, bearish_engulfing_df: pd.DataFrame) -> None:
        df = add_all(bearish_engulfing_df)
        assert bullish_engulfing(df) is None


class TestBearishEngulfing:
    def test_detects_pattern(self, bearish_engulfing_df: pd.DataFrame) -> None:
        df = add_all(bearish_engulfing_df)
        result = bearish_engulfing(df)
        assert result is not None
        assert result.name == "Bearish Engulfing"

    def test_no_signal_on_bullish(self, bullish_engulfing_df: pd.DataFrame) -> None:
        df = add_all(bullish_engulfing_df)
        assert bearish_engulfing(df) is None


class TestDoji:
    def test_detects_doji(self) -> None:
        # Candle where body is ~1% of full range
        import numpy as np
        import pandas as pd

        closes = [100.0] * 89 + [100.02]
        opens = [100.0] * 89 + [100.00]
        highs = [100.5] * 89 + [102.0]   # wide range
        lows = [99.5] * 89 + [98.0]
        vols = [1_000_000.0] * 90
        idx = pd.date_range("2024-01-01", periods=90, freq="B")
        df = pd.DataFrame(
            {"Open": opens, "High": highs, "Low": lows, "Close": closes, "Volume": vols},
            index=idx,
        )
        df = add_all(df)
        result = doji(df)
        assert result is not None
        assert result.name == "Doji"

    def test_no_doji_for_large_body(self, bullish_engulfing_df: pd.DataFrame) -> None:
        df = add_all(bullish_engulfing_df)
        assert doji(df) is None


class TestInsideBar:
    def test_detects_inside_bar(self) -> None:
        import pandas as pd

        closes = [100.0] * 88 + [101.0, 100.5]
        opens = [100.0] * 88 + [99.0, 99.8]
        highs = [100.5] * 88 + [102.0, 101.5]    # today < yesterday
        lows = [99.5] * 88 + [98.0, 98.5]         # today > yesterday
        vols = [1_000_000.0] * 90
        idx = pd.date_range("2024-01-01", periods=90, freq="B")
        df = pd.DataFrame(
            {"Open": opens, "High": highs, "Low": lows, "Close": closes, "Volume": vols},
            index=idx,
        )
        df = add_all(df)
        result = inside_bar(df)
        assert result is not None
        assert result.name == "Inside Bar"
