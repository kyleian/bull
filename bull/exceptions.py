"""
Custom exceptions for Bull scanner.
All application errors inherit from BullError for easy top-level catching.
"""

from __future__ import annotations


class BullError(Exception):
    """Base exception for all Bull errors."""


# ── Data layer ────────────────────────────────────────────────────────────────


class TickerFetchError(BullError):
    """Raised when the S&P 500 ticker list cannot be retrieved."""


class MarketDataError(BullError):
    """Raised when price/volume history cannot be fetched for a symbol."""

    def __init__(self, ticker: str, reason: str) -> None:
        super().__init__(f"[{ticker}] {reason}")
        self.ticker = ticker
        self.reason = reason


class InsufficientDataError(MarketDataError):
    """Raised when a ticker has too few trading days to calculate indicators."""


# ── Analysis layer ────────────────────────────────────────────────────────────


class AnalysisError(BullError):
    """Raised when a technical analysis calculation fails unexpectedly."""


class ScannerError(BullError):
    """Raised when the high-level scanner loop encounters a fatal error."""


# ── Config / reporting ────────────────────────────────────────────────────────


class ConfigError(BullError):
    """Raised when required configuration is missing or invalid."""


class ReportError(BullError):
    """Raised when a report cannot be generated or delivered."""
