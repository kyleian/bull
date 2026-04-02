# 🐂 Bull — S&P 500 Market Scanner

[![CI](https://github.com/kyleian/bull/actions/workflows/ci.yml/badge.svg)](https://github.com/kyleian/bull/actions/workflows/ci.yml)
[![Docker](https://github.com/kyleian/bull/actions/workflows/docker.yml/badge.svg)](https://github.com/kyleian/bull/actions/workflows/docker.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

A modular, multi-mode S&P 500 scanner that identifies **bullish**, **bearish**, and **neutral** setups from technical pattern analysis. Reports actionable trade plans with entry/target/stop levels and options guidance.

> **Not financial advice.** All output is for educational and informational purposes only. Always do your own due diligence.

---

## Features

| Capability | Detail |
|---|---|
| **Multi-mode scanning** | `bullish`, `bearish`, `neutral`, or `all` |
| **Pattern library** | Bullish/bearish engulfing, hammer, shooting star, RSI bounces, MACD crosses, golden/death cross, Bollinger Band breakouts, inside bar, doji, consolidation squeeze |
| **Composite scoring** | 0–10 weighted score per signal; 1–5 star display |
| **Trade plan** | Entry, 1.5R quick target, 2.5R extended target, ATR-based stop |
| **Options guidance** | ITM/ATM/OTM strike suggestions, 2 nearest expiry dates, estimated profit % |
| **Flexible output** | Rich terminal table, JSON, or HTML email |
| **Scheduled CI/CD** | GitHub Actions runs daily at 4:15 PM ET on weekdays |
| **Containerised** | Multi-arch Docker image (amd64 + arm64) published to GHCR |

---

## Quickstart

### Install locally

```bash
git clone https://github.com/kyleian/bull
cd bull
python -m venv .venv && source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -e .
```

### Run a scan

```bash
# Full S&P 500 scan, all modes, console output (default)
bull scan

# Bullish signals only
bull scan --mode bullish

# Bearish, output as JSON
bull scan --mode bearish --output json

# Scan specific tickers
bull scan --tickers AAPL,MSFT,NVDA,TSLA

# Send results via email
bull scan --mode all --output email

# Debug mode
bull scan --mode bullish -v
```

### Via Docker

```bash
# Pull latest image from GHCR
docker pull ghcr.io/kyleian/bull:latest

# Run scan (console output)
docker run --rm ghcr.io/kyleian/bull:latest

# Custom mode + email output
docker run --rm \
  -e BULL_SCAN_MODE=bearish \
  -e BULL_OUTPUT_FORMAT=email \
  -e BULL_GMAIL_ADDRESS=you@gmail.com \
  -e BULL_GMAIL_APP_PASSWORD=xxxx-xxxx-xxxx-xxxx \
  -e BULL_TO_EMAIL=recipient@example.com \
  ghcr.io/kyleian/bull:latest
```

### Via Docker Compose

```bash
cp .env.example .env
# Edit .env with your settings
docker compose up
```

---

## Configuration

All settings are controlled via environment variables (prefix `BULL_`) or a `.env` file.
See [`.env.example`](.env.example) for the full list.

| Variable | Default | Description |
|---|---|---|
| `BULL_SCAN_MODE` | `all` | `all \| bullish \| bearish \| neutral` |
| `BULL_OUTPUT_FORMAT` | `console` | `console \| json \| email` |
| `BULL_CONCURRENCY` | `10` | Parallel fetch threads (1–50) |
| `BULL_HISTORY_DAYS` | `90` | Days of price history to fetch |
| `BULL_MIN_SIGNAL_SCORE` | `1.5` | Minimum composite score (0–10) |
| `BULL_MIN_BODY_PCT` | `0.8` | Min candlestick body % |
| `BULL_MIN_VOLUME_RATIO` | `1.10` | Min volume vs 20-day average |
| `BULL_GMAIL_ADDRESS` | — | Gmail sender (email output only) |
| `BULL_GMAIL_APP_PASSWORD` | — | Gmail app password |
| `BULL_TO_EMAIL` | — | Recipient (defaults to sender) |

---

## Architecture

```
bull/
├── cli.py              ← Click command group — `bull scan`
├── config.py           ← pydantic-settings configuration
├── scanner.py          ← Threading scan loop; orchestrates all modes
├── scoring.py          ← Weighted composite 0–10 score engine
├── exceptions.py       ← Typed exception hierarchy
├── __version__.py
│
├── data/
│   ├── tickers.py      ← S&P 500 list via Wikipedia (+ fallback)
│   └── market.py       ← yfinance wrapper; returns MarketData
│
├── analysis/
│   ├── technical.py    ← Pure indicator functions (MA, MACD, RSI, ATR, BB)
│   ├── patterns.py     ← Stateless pattern detectors → PatternMatch | None
│   ├── _shared.py      ← Signal assembly helpers shared by all modes
│   ├── bullish.py      ← Bullish mode scanner
│   ├── bearish.py      ← Bearish mode scanner
│   └── neutral.py      ← Neutral / consolidation scanner
│
├── models/
│   └── signal.py       ← Signal, ScanResult, Indicators, PatternMatch
│
└── reporters/
    ├── console.py      ← Rich terminal tables
    ├── json_report.py  ← JSON stdout / file
    └── email.py        ← Jinja2 HTML email via Gmail SMTP
```

### Extending

**Add a new pattern:**
1. Write a detector function in `bull/analysis/patterns.py` — signature: `(df: pd.DataFrame) -> PatternMatch | None`
2. Add `(your_fn, weight)` to the `_DETECTORS` list in the relevant scanner (`bullish.py`, `bearish.py`, or `neutral.py`)
3. Add tests in `tests/test_patterns.py`

**Add a new scan mode:**
1. Create `bull/analysis/mymode.py` with a `scan_mymode(data: MarketData) -> Signal | None` function
2. Register it in `bull/scanner.py`'s `_MODE_FN` dict
3. Add the enum value to `ScanMode` in `bull/config.py`

---

## Patterns Reference

### Bullish Mode
| Pattern | Description | Weight |
|---|---|---|
| **Bullish Engulfing** | ≥3 red days followed by an engulfing green candle with elevated volume | 3.0 |
| **Hammer** | Small body at top, lower wick ≥2× body after downtrend | 2.0 |
| **RSI Oversold Bounce** | RSI recovering from below 35 | 2.0 |
| **MACD Bullish Cross** | MACD line crossed above signal line | 1.5 |
| **Golden Cross** | SMA-50 crossed above SMA-200 | 2.5 |
| **BB Breakout Up** | Close broke above upper Bollinger Band | 1.5 |

### Bearish Mode
| Pattern | Description | Weight |
|---|---|---|
| **Bearish Engulfing** | ≥3 green days followed by an engulfing red candle | 3.0 |
| **Shooting Star** | Small body at bottom, upper wick ≥2× body after uptrend | 2.0 |
| **RSI Overbought Reversal** | RSI fading from above 65 | 2.0 |
| **MACD Bearish Cross** | MACD line crossed below signal line | 1.5 |
| **Death Cross** | SMA-50 crossed below SMA-200 | 2.5 |
| **BB Breakdown** | Close broke below lower Bollinger Band | 1.5 |

### Neutral Mode
| Pattern | Description | Weight |
|---|---|---|
| **Inside Bar** | Today's full range contained within yesterday's | 2.0 |
| **Doji** | Body ≤10% of full range — indecision | 1.5 |
| **Consolidation Range** | 5-day ATR ≤50% of 20-day ATR (tight squeeze) | 3.0 |

---

## Development

```bash
pip install -e ".[dev]"

# Lint
ruff check bull/ tests/

# Tests with coverage
pytest

# Type check
mypy bull/
```

---

## CI/CD

| Workflow | Trigger | Action |
|---|---|---|
| `ci.yml` | Push / PR to `main` | Lint, type check, tests on Python 3.11 & 3.12 |
| `docker.yml` | Push to `main` or version tag | Build multi-arch image → GHCR |
| `scan.yml` | Weekdays 4:15 PM ET; manual dispatch | Run scan, send email |

Docker images are published to `ghcr.io/kyleian/bull` with `main`, `sha-*`, and semver tags.

---

## Roadmap

- [ ] Momentum scoring with news sentiment (RSS / Benzinga)
- [ ] Sector rotation heatmap output
- [ ] Slack / Discord webhook reporter
- [ ] Backtesting harness to validate signal quality
- [ ] Web dashboard (FastAPI + HTMX)

---

## Credits

Inspired by [chrisbynum/sp500-scanner](https://github.com/chrisbynum/sp500-scanner) — a clean daily bullish engulfing pattern scanner.

---

## License

[MIT](LICENSE)