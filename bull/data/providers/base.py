"""Abstract base class for all market data providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import pandas as pd


@dataclass(slots=True)
class MarketData:
    """All raw data for a single ticker ready for analysis."""

    ticker: str
    df: pd.DataFrame           # OHLCV history, date-indexed, timezone-naive
    company_name: str = "Unknown"
    sector: str = "Unknown"
    description: str = ""
    news_headlines: list[str] = field(default_factory=list)  # recent headlines


class BaseProvider(ABC):
    """Interface all data providers must implement."""

    @abstractmethod
    def fetch(self, ticker: str) -> MarketData:
        """Fetch OHLCV + metadata for *ticker*.

        Raises
        ------
        MarketDataError
            On any network or parse failure.
        InsufficientDataError
            When too few rows are available.
        """
