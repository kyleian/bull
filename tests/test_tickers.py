"""Tests for bull.data.tickers"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from bull.data.tickers import _FALLBACK_TICKERS, get_sp500_tickers


class TestGetSp500Tickers:
    def test_returns_list_of_strings(self) -> None:
        # Must always return at least the fallback list
        tickers = get_sp500_tickers()
        assert isinstance(tickers, list)
        assert all(isinstance(t, str) for t in tickers)

    def test_fallback_used_on_network_error(self) -> None:
        # Clear lru_cache so the fallback path is exercised
        get_sp500_tickers.cache_clear()
        with patch("bull.data.tickers.requests.get", side_effect=ConnectionError("timeout")):
            tickers = get_sp500_tickers()
        assert tickers == sorted(set(_FALLBACK_TICKERS))
        get_sp500_tickers.cache_clear()  # clean up for other tests

    def test_tickers_are_sorted_and_deduped(self) -> None:
        get_sp500_tickers.cache_clear()
        with patch("bull.data.tickers.requests.get", side_effect=ConnectionError):
            tickers = get_sp500_tickers()
        assert tickers == sorted(set(tickers))
        get_sp500_tickers.cache_clear()

    def test_dots_replaced_with_hyphens(self) -> None:
        # BRK.B should become BRK-B in real data
        get_sp500_tickers.cache_clear()
        mock_response = MagicMock()
        mock_response.content = b"""
        <table><tr><th>Symbol</th></tr>
        <tr><td>BRK.B</td></tr>
        <tr><td>AAPL</td></tr>
        </table>
        """
        mock_response.raise_for_status = MagicMock()
        with patch("bull.data.tickers.requests.get", return_value=mock_response):
            with patch("bull.data.tickers.pd.read_html") as mock_read_html:
                import pandas as pd
                mock_read_html.return_value = [pd.DataFrame({"Symbol": ["BRK.B", "AAPL"]})]
                tickers = get_sp500_tickers()
        assert "BRK-B" in tickers
        assert "BRK.B" not in tickers
        get_sp500_tickers.cache_clear()
