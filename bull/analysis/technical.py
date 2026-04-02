"""
Technical indicator computation.

All functions accept a DataFrame with OHLCV columns (as returned by yfinance)
and return a new DataFrame with additional indicator columns.  Functions are
pure — no side-effects, no logging.

Column naming convention: snake_case, lowercase.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from bull.exceptions import AnalysisError


# ─────────────────────────────── helpers ────────────────────────────────────


def _require_cols(df: pd.DataFrame, *cols: str) -> None:
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise AnalysisError(f"DataFrame missing required columns: {missing}")


# ─────────────────────────────── indicators ─────────────────────────────────


def add_moving_averages(df: pd.DataFrame) -> pd.DataFrame:
    """Add SMA_20, SMA_50, SMA_200, EMA_12, EMA_26."""
    _require_cols(df, "Close")
    df = df.copy()
    df["SMA_20"] = df["Close"].rolling(20).mean()
    df["SMA_50"] = df["Close"].rolling(50).mean()
    df["SMA_200"] = df["Close"].rolling(200).mean()
    df["EMA_12"] = df["Close"].ewm(span=12, adjust=False).mean()
    df["EMA_26"] = df["Close"].ewm(span=26, adjust=False).mean()
    return df


def add_macd(df: pd.DataFrame) -> pd.DataFrame:
    """Add MACD_line, MACD_signal (9-period EMA), MACD_hist."""
    _require_cols(df, "EMA_12", "EMA_26")
    df = df.copy()
    df["MACD_line"] = df["EMA_12"] - df["EMA_26"]
    df["MACD_signal"] = df["MACD_line"].ewm(span=9, adjust=False).mean()
    df["MACD_hist"] = df["MACD_line"] - df["MACD_signal"]
    return df


def add_rsi(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """Add RSI_{period} using Wilder's smoothing (standard)."""
    _require_cols(df, "Close")
    df = df.copy()
    delta = df["Close"].diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    df[f"RSI_{period}"] = 100.0 - (100.0 / (1.0 + rs))
    return df


def add_atr(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """Add ATR_{period} (Average True Range)."""
    _require_cols(df, "High", "Low", "Close")
    df = df.copy()
    hl = df["High"] - df["Low"]
    hc = (df["High"] - df["Close"].shift(1)).abs()
    lc = (df["Low"] - df["Close"].shift(1)).abs()
    df["TR"] = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    df[f"ATR_{period}"] = df["TR"].rolling(period).mean()
    return df


def add_bollinger_bands(df: pd.DataFrame, period: int = 20, std: float = 2.0) -> pd.DataFrame:
    """Add BB_upper, BB_lower, BB_mid."""
    _require_cols(df, "Close")
    df = df.copy()
    df["BB_mid"] = df["Close"].rolling(period).mean()
    rolling_std = df["Close"].rolling(period).std()
    df["BB_upper"] = df["BB_mid"] + std * rolling_std
    df["BB_lower"] = df["BB_mid"] - std * rolling_std
    return df


def add_volume_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Add Avg_Volume_20 and Volume_ratio."""
    _require_cols(df, "Volume")
    df = df.copy()
    df["Avg_Volume_20"] = df["Volume"].rolling(20).mean()
    df["Volume_ratio"] = df["Volume"] / df["Avg_Volume_20"]
    return df


def add_all(df: pd.DataFrame) -> pd.DataFrame:
    """Apply all technical indicators in dependency order."""
    df = add_moving_averages(df)
    df = add_macd(df)
    df = add_rsi(df)
    df = add_atr(df)
    df = add_bollinger_bands(df)
    df = add_volume_indicators(df)
    return df
