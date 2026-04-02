"""
Application configuration via environment variables or .env file.
Override any field by setting the corresponding env var (prefix: BULL_).
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ScanMode(StrEnum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"
    ALL = "all"


class OutputFormat(StrEnum):
    CONSOLE = "console"
    JSON = "json"
    EMAIL = "email"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="BULL_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Scan behaviour ────────────────────────────────────────────────────────
    scan_mode: ScanMode = ScanMode.ALL
    output_format: OutputFormat = OutputFormat.CONSOLE
    concurrency: int = Field(default=10, ge=1, le=50)

    # ── Data fetching ─────────────────────────────────────────────────────────
    history_days: int = Field(default=90, ge=30)
    min_history_rows: int = Field(default=52, ge=30)  # need >50 for MA_50

    # ── Signal filters ────────────────────────────────────────────────────────
    min_body_pct: float = Field(default=0.8, ge=0.0)
    min_volume_ratio: float = Field(default=1.10, ge=1.0)
    min_signal_score: float = Field(default=1.5, ge=0.0)
    min_results: int = Field(default=5, ge=1)  # always surface at least this many picks per mode

    # ── Email output (only required when output_format=email) ─────────────────
    gmail_address: str | None = None
    gmail_app_password: str | None = None
    to_email: str | None = None

    @field_validator("to_email", mode="before")
    @classmethod
    def default_to_email(cls, v: str | None, info: object) -> str | None:  # noqa: ARG003
        return v  # resolved lazily against gmail_address in the reporter

    # ── Convenience ───────────────────────────────────────────────────────────
    @property
    def email_configured(self) -> bool:
        return bool(self.gmail_address and self.gmail_app_password)

    @property
    def effective_to_email(self) -> str | None:
        return self.to_email or self.gmail_address


# Singleton — import and use everywhere
settings = Settings()
