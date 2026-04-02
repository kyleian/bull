"""
Signal and recommendation data models.

These are plain dataclasses (stdlib) to avoid forcing pydantic on callers that
only import models.  JSON serialisation helpers are included for free via
`dataclasses.asdict`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Literal

ScanMode = Literal["bullish", "bearish", "neutral"]


@dataclass(slots=True)
class Indicators:
    """Pre-computed technical indicators for a single ticker."""

    sma_20: float
    sma_50: float
    sma_200: float
    rsi_14: float
    macd_line: float
    macd_signal: float
    macd_hist: float
    atr_14: float
    bb_upper: float
    bb_lower: float
    bb_mid: float
    volume_ratio: float          # last close volume / 20-day avg volume
    distance_from_sma50: float   # % distance of close from SMA-50
    distance_from_sma200: float  # % distance of close from SMA-200


@dataclass(slots=True)
class PatternMatch:
    """A single detected candlestick / structural pattern."""

    name: str
    strength: float     # 0.0 – 1.0
    description: str


@dataclass(slots=True)
class Signal:
    """A complete trading signal for a single ticker."""

    ticker: str
    company_name: str
    sector: str
    description: str                    # short business summary
    mode: ScanMode
    signal_date: date

    current_price: float
    entry_price: float
    target_quick: float                 # 1.5R target (3-5 day hold)
    target_extended: float              # 2.5R target (5-10 day hold)
    stop_loss: float

    indicators: Indicators
    patterns: list[PatternMatch]

    score: float                        # 0.0 – 10.0 composite score
    stars: int                          # 1 – 5 rounded display rating
    above_threshold: bool               # True = confirmed signal; False = best available pick

    rationale: list[str]                # human-readable bullet points
    risk_reward: float                  # quick target R:R ratio

    option_expirations: list[str] = field(default_factory=list)
    suggested_strikes: dict[str, float] = field(default_factory=dict)
    expected_option_profit_pct: float = 0.0

    weekly_resistance: float = 0.0
    body_size_pct: float = 0.0
    red_days_prior: int = 0

    @property
    def star_display(self) -> str:
        return "★" * self.stars + "☆" * (5 - self.stars)


@dataclass(slots=True)
class ScanResult:
    """Aggregated result from a full scan run."""

    mode: str
    total_scanned: int
    total_signals: int
    signals: list[Signal]
    errors: dict[str, str] = field(default_factory=dict)   # ticker → error msg
    scan_date: date = field(default_factory=date.today)

    @property
    def sector_summary(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for sig in self.signals:
            counts[sig.sector] = counts.get(sig.sector, 0) + 1
        return dict(sorted(counts.items(), key=lambda kv: kv[1], reverse=True))
