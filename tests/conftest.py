"""
Shared pytest fixtures for Bull test suite.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest


def _make_ohlcv(
    closes: list[float],
    opens: list[float] | None = None,
    highs: list[float] | None = None,
    lows: list[float] | None = None,
    volumes: list[float] | None = None,
) -> pd.DataFrame:
    """Build a minimal OHLCV DataFrame for testing."""
    n = len(closes)
    closes_arr = np.array(closes, dtype=float)
    opens_arr = np.array(opens, dtype=float) if opens else closes_arr * 0.99
    highs_arr = np.array(highs, dtype=float) if highs else closes_arr * 1.01
    lows_arr = np.array(lows, dtype=float) if lows else closes_arr * 0.98
    vols_arr = np.array(volumes, dtype=float) if volumes else np.full(n, 1_000_000.0)

    idx = pd.date_range("2024-01-01", periods=n, freq="B")
    return pd.DataFrame(
        {"Open": opens_arr, "High": highs_arr, "Low": lows_arr,
         "Close": closes_arr, "Volume": vols_arr},
        index=idx,
    )


@pytest.fixture
def bullish_engulfing_df() -> pd.DataFrame:
    """
    90-row DataFrame ending with a clean bullish engulfing pattern:
    4 red days followed by a large green candle with high volume.
    """
    base = 100.0
    # First 85 rows: flat close ~ 100
    closes = [base] * 85
    opens = [base] * 85
    vols = [1_000_000.0] * 85

    # 4 red days (close < open)
    for _ in range(4):
        opens.append(base)
        closes.append(base - 1.5)
        vols.append(1_000_000.0)
        base -= 1.5

    # Bullish engulfing: opens below prior close, closes well above prior open
    opens.append(base - 0.5)       # open below prior close
    closes.append(base + 5.0)      # close above prior open
    vols.append(2_000_000.0)       # high volume

    n = len(closes)
    highs = [max(o, c) + 0.1 for o, c in zip(opens, closes)]
    lows = [min(o, c) - 0.1 for o, c in zip(opens, closes)]

    return _make_ohlcv(closes, opens, highs, lows, vols)


@pytest.fixture
def bearish_engulfing_df() -> pd.DataFrame:
    """90-row DataFrame ending with a clean bearish engulfing pattern."""
    base = 100.0
    closes = [base] * 85
    opens = [base] * 85
    vols = [1_000_000.0] * 85

    # 4 green days
    for _ in range(4):
        opens.append(base)
        closes.append(base + 1.5)
        vols.append(1_000_000.0)
        base += 1.5

    # Bearish engulfing
    opens.append(base + 0.5)
    closes.append(base - 5.0)
    vols.append(2_000_000.0)

    n = len(closes)
    highs = [max(o, c) + 0.1 for o, c in zip(opens, closes)]
    lows = [min(o, c) - 0.1 for o, c in zip(opens, closes)]

    return _make_ohlcv(closes, opens, highs, lows, vols)


@pytest.fixture
def flat_df() -> pd.DataFrame:
    """90-row completely flat DataFrame — no patterns should fire."""
    n = 90
    return _make_ohlcv(
        closes=[100.0] * n,
        opens=[100.0] * n,
        highs=[100.5] * n,
        lows=[99.5] * n,
        volumes=[1_000_000.0] * n,
    )
