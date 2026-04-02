"""
Sentiment analysis engine.

Sources (all free or included in Tiingo subscription):
  1. News headlines — yfinance news (already fetched) or Tiingo news API
  2. Yahoo Finance RSS feed — free, no key, always available
  3. StockTwits social stream — free public API, no key required
  4. Finnhub news sentiment — free tier with BULL_FINNHUB_API_KEY (optional)

Returns a SentimentData object scored -1.0 (very bearish) to +1.0 (very bullish).
"""

from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from functools import lru_cache

import requests

log = logging.getLogger(__name__)

_SESSION = requests.Session()
_SESSION.headers.update({"User-Agent": "bull-scanner/0.1 (+https://github.com/kyleian/bull)"})

# ── Financial sentiment lexicon ───────────────────────────────────────────────
# Words weighted by directional impact. Weights are -1.0 (bearish) to +1.0
# (bullish). Compound phrases take priority over single words.

_BULLISH_PHRASES: list[tuple[str, float]] = [
    # Strong positive
    ("beats estimates", 1.0), ("record revenue", 1.0), ("record earnings", 1.0),
    ("raises guidance", 1.0), ("buyback", 0.8), ("share repurchase", 0.8),
    ("dividend increase", 0.9), ("special dividend", 0.7), ("acquisition", 0.6),
    ("partnership", 0.5), ("fda approval", 1.0), ("regulatory approval", 0.9),
    ("strong demand", 0.8), ("outperform", 0.7), ("upgrade", 0.8),
    ("price target raised", 0.9), ("buy rating", 0.8), ("overweight", 0.7),
    ("beat expectations", 0.9), ("positive outlook", 0.7), ("strong growth", 0.8),
    ("market share gain", 0.7), ("new product", 0.5), ("expansion", 0.5),
    ("analyst upgrade", 0.8), ("bullish", 0.7), ("rally", 0.6),
    ("breakthrough", 0.7), ("innovation", 0.4), ("profitability", 0.5),
    ("revenue growth", 0.6), ("earnings growth", 0.7),
]

_BEARISH_PHRASES: list[tuple[str, float]] = [
    # Strong negative
    ("misses estimates", -1.0), ("lowers guidance", -1.0), ("cuts guidance", -1.0),
    ("job cuts", -0.8), ("layoffs", -0.8), ("bankruptcy", -1.0), ("default", -0.9),
    ("recall", -0.7), ("fda rejection", -1.0), ("regulatory rejection", -0.9),
    ("weak demand", -0.8), ("underperform", -0.8), ("downgrade", -0.9),
    ("price target cut", -0.9), ("sell rating", -0.9), ("underweight", -0.7),
    ("missed expectations", -0.9), ("negative outlook", -0.7), ("disappointing", -0.7),
    ("market share loss", -0.7), ("investigation", -0.7), ("lawsuit", -0.6),
    ("fraud", -1.0), ("write-down", -0.8), ("impairment", -0.7),
    ("earnings miss", -0.9), ("revenue decline", -0.7), ("loss widens", -0.8),
    ("bearish", -0.7), ("selloff", -0.6), ("decline", -0.4), ("drop", -0.3),
    ("tariff", -0.5), ("trade war", -0.6), ("inflation concern", -0.5),
    ("interest rate", -0.3), ("stagflation", -0.7), ("recession", -0.7),
]


@dataclass
class SentimentData:
    """Aggregated sentiment for a single ticker."""

    score: float = 0.0               # -1.0 very bearish → +1.0 very bullish
    direction: str = "neutral"       # "bullish" | "bearish" | "neutral"
    confidence: float = 0.0          # 0.0 – 1.0 (how much data we had)
    headline_count: int = 0
    social_bulls: int = 0
    social_bears: int = 0
    top_headlines: list[str] = field(default_factory=list)
    catalyst_summary: str = ""       # one-line human-readable explanation


def analyse(ticker: str, news_headlines: list[str]) -> SentimentData:
    """
    Build a SentimentData for *ticker* by combining:
      1. Pre-fetched *news_headlines* from the data provider
      2. Yahoo Finance RSS (free)
      3. StockTwits social sentiment (free, no key)
    """
    all_headlines = list(news_headlines)

    # ── Supplement with Yahoo Finance RSS ────────────────────────────────────
    try:
        rss_headlines = _fetch_yahoo_rss(ticker)
        all_headlines.extend(rss_headlines)
    except Exception as exc:
        log.debug("[%s] Yahoo RSS failed (non-fatal): %s", ticker, exc)

    # ── Deduplicate headlines ─────────────────────────────────────────────────
    seen: set[str] = set()
    unique: list[str] = []
    for h in all_headlines:
        key = h.lower()[:60]
        if key not in seen:
            seen.add(key)
            unique.append(h)
    all_headlines = unique[:15]

    # ── Score headlines ───────────────────────────────────────────────────────
    news_score = _score_headlines(all_headlines)

    # ── StockTwits social sentiment ───────────────────────────────────────────
    social_bulls = 0
    social_bears = 0
    try:
        social_bulls, social_bears = _fetch_stocktwits_sentiment(ticker)
    except Exception as exc:
        log.debug("[%s] StockTwits failed (non-fatal): %s", ticker, exc)

    social_total = social_bulls + social_bears
    social_score = 0.0
    if social_total >= 5:
        social_score = (social_bulls - social_bears) / social_total

    # ── Combine scores (news 60%, social 40%) ────────────────────────────────
    news_weight = 0.6 if all_headlines else 0.0
    social_weight = 0.4 if social_total >= 5 else 0.0
    total_weight = news_weight + social_weight

    if total_weight > 0:
        # Normalise weights
        w_n = news_weight / total_weight
        w_s = social_weight / total_weight
        combined = (news_score * w_n) + (social_score * w_s)
    else:
        combined = 0.0

    direction = (
        "bullish" if combined >= 0.15
        else "bearish" if combined <= -0.15
        else "neutral"
    )

    confidence = min(1.0, (len(all_headlines) / 10) * 0.7 + (min(social_total, 50) / 50) * 0.3)

    catalyst = _build_catalyst_summary(all_headlines, combined, social_bulls, social_bears)

    return SentimentData(
        score=round(combined, 3),
        direction=direction,
        confidence=round(confidence, 2),
        headline_count=len(all_headlines),
        social_bulls=social_bulls,
        social_bears=social_bears,
        top_headlines=all_headlines[:5],
        catalyst_summary=catalyst,
    )


# ── Internal helpers ──────────────────────────────────────────────────────────

def _score_headlines(headlines: list[str]) -> float:
    """Score a list of headlines, returning average signed score."""
    if not headlines:
        return 0.0
    scores = [_score_single_headline(h) for h in headlines]
    return sum(scores) / len(scores)


def _score_single_headline(text: str) -> float:
    """Return a -1 to +1 score for a single headline using the lexicon."""
    lower = text.lower()
    score = 0.0
    hits = 0

    # Check bullish phrases first (longer phrases first for priority)
    for phrase, weight in sorted(_BULLISH_PHRASES, key=lambda x: -len(x[0])):
        if phrase in lower:
            score += weight
            hits += 1
            break  # one strongest match per direction per headline

    for phrase, weight in sorted(_BEARISH_PHRASES, key=lambda x: -len(x[0])):
        if phrase in lower:
            score += weight
            hits += 1
            break

    return max(-1.0, min(1.0, score))


@lru_cache(maxsize=256)
def _fetch_yahoo_rss(ticker: str) -> list[str]:
    """Fetch headlines from Yahoo Finance RSS (free, no auth)."""
    url = f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={ticker}&region=US&lang=en-US"
    resp = _SESSION.get(url, timeout=8)
    resp.raise_for_status()
    root = ET.fromstring(resp.content)
    ns = ""
    headlines: list[str] = []
    for item in root.iter("item"):
        title = item.find(f"{ns}title")
        if title is not None and title.text:
            headlines.append(title.text.strip())
    return headlines[:10]


@lru_cache(maxsize=256)
def _fetch_stocktwits_sentiment(ticker: str) -> tuple[int, int]:
    """
    Return (bullish_count, bearish_count) from StockTwits recent stream.
    Free public API, no key required.
    """
    # StockTwits uses different ticker format (BRK-B -> BRK.B)
    st_ticker = ticker.replace("-", ".")
    url = f"https://api.stocktwits.com/api/2/streams/symbol/{st_ticker}.json"
    resp = _SESSION.get(url, timeout=8, params={"limit": 30})
    if resp.status_code == 429:
        log.debug("[%s] StockTwits rate limited", ticker)
        return 0, 0
    if resp.status_code != 200:
        return 0, 0
    data = resp.json()
    messages = data.get("messages") or []
    bulls = 0
    bears = 0
    for msg in messages:
        sentiment = (msg.get("entities") or {}).get("sentiment") or {}
        basic = (sentiment.get("basic") or "").lower()
        if basic == "bullish":
            bulls += 1
        elif basic == "bearish":
            bears += 1
    return bulls, bears


def _build_catalyst_summary(
    headlines: list[str],
    score: float,
    bulls: int,
    bears: int,
) -> str:
    """Build a one-line human-readable catalyst summary."""
    direction_word = "Positive" if score >= 0.15 else "Negative" if score <= -0.15 else "Mixed"
    parts: list[str] = []

    top = headlines[0] if headlines else None
    if top:
        # Trim to ~80 chars
        trimmed = top if len(top) <= 80 else top[:77] + "..."
        parts.append(f"{direction_word} news: {trimmed}")
    else:
        parts.append(f"{direction_word} sentiment (no recent headlines found)")

    total = bulls + bears
    if total >= 5:
        pct = round(bulls / total * 100)
        parts.append(f"Social: {pct}% bullish ({bulls}B/{bears}Be on StockTwits)")

    return " | ".join(parts)
