"""Tests for bull.analysis.technical"""

from __future__ import annotations

import math

import pytest
import pandas as pd

from bull.analysis.technical import (
    add_all,
    add_atr,
    add_bollinger_bands,
    add_macd,
    add_moving_averages,
    add_rsi,
    add_volume_indicators,
)
from bull.exceptions import AnalysisError


def _simple_df(n: int = 90, price: float = 100.0) -> pd.DataFrame:
    import numpy as np

    prices = [price + i * 0.1 for i in range(n)]
    idx = pd.date_range("2024-01-01", periods=n, freq="B")
    return pd.DataFrame(
        {
            "Open": [p * 0.99 for p in prices],
            "High": [p * 1.01 for p in prices],
            "Low": [p * 0.98 for p in prices],
            "Close": prices,
            "Volume": [1_000_000.0] * n,
        },
        index=idx,
    )


class TestMovingAverages:
    def test_columns_added(self) -> None:
        df = add_moving_averages(_simple_df())
        assert all(c in df.columns for c in ["SMA_20", "SMA_50", "EMA_12", "EMA_26"])

    def test_sma_200_requires_enough_data(self) -> None:
        df = add_moving_averages(_simple_df(90))
        # SMA_200 should all be NaN for only 90 rows
        assert df["SMA_200"].isna().all()

    def test_sma_20_non_nan_after_20_rows(self) -> None:
        df = add_moving_averages(_simple_df(90))
        assert not math.isnan(float(df["SMA_20"].iloc[-1]))


class TestRSI:
    def test_rsi_range(self) -> None:
        df = add_rsi(_simple_df(90))
        valid = df["RSI_14"].dropna()
        assert (valid >= 0).all() and (valid <= 100).all()

    def test_rsi_column_exists(self) -> None:
        df = add_rsi(_simple_df())
        assert "RSI_14" in df.columns


class TestMACD:
    def test_macd_columns(self) -> None:
        df = add_moving_averages(_simple_df())
        df = add_macd(df)
        assert all(c in df.columns for c in ["MACD_line", "MACD_signal", "MACD_hist"])

    def test_raises_without_emas(self) -> None:
        with pytest.raises(AnalysisError):
            add_macd(_simple_df())


class TestATR:
    def test_atr_positive(self) -> None:
        df = add_atr(_simple_df())
        valid = df["ATR_14"].dropna()
        assert (valid > 0).all()


class TestBollingerBands:
    def test_bb_columns(self) -> None:
        df = add_bollinger_bands(_simple_df())
        assert all(c in df.columns for c in ["BB_upper", "BB_lower", "BB_mid"])

    def test_upper_above_lower(self) -> None:
        df = add_bollinger_bands(_simple_df())
        valid = df.dropna(subset=["BB_upper", "BB_lower"])
        assert (valid["BB_upper"] > valid["BB_lower"]).all()


class TestVolumeIndicators:
    def test_volume_ratio_column(self) -> None:
        df = add_volume_indicators(_simple_df())
        assert "Volume_ratio" in df.columns

    def test_volume_ratio_positive(self) -> None:
        df = add_volume_indicators(_simple_df())
        valid = df["Volume_ratio"].dropna()
        assert (valid > 0).all()


class TestAddAll:
    def test_all_columns_present(self) -> None:
        df = add_all(_simple_df(90))
        expected = [
            "SMA_20", "SMA_50", "EMA_12", "EMA_26",
            "MACD_line", "MACD_signal", "MACD_hist",
            "RSI_14", "ATR_14",
            "BB_upper", "BB_lower", "BB_mid",
            "Volume_ratio",
        ]
        missing = [c for c in expected if c not in df.columns]
        assert not missing, f"Missing columns: {missing}"
