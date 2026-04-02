"""
Bull CLI entrypoint.

Usage
-----
  bull scan                      # scan all modes, console output
  bull scan --mode bullish        # bullish only
  bull scan --mode bearish        # bearish only
  bull scan --mode neutral        # neutral / consolidation only
  bull scan --output json         # JSON to stdout
  bull scan --output json --out-file results.json
  bull scan --output email        # HTML email (requires env creds)
  bull scan --tickers AAPL,MSFT   # scan a specific subset
  bull scan --concurrency 20      # override thread count
  bull --version                  # print version and exit
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import click

from bull.__version__ import __version__
from bull.config import OutputFormat, ScanMode, Universe

log = logging.getLogger(__name__)


def _configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        level=level,
        stream=sys.stderr,
    )
    # Quieten noisy third-party loggers
    logging.getLogger("yfinance").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("peewee").setLevel(logging.WARNING)


# ──────────────────────────── CLI definition ────────────────────────────────


@click.group()
@click.version_option(__version__, prog_name="bull")
def main() -> None:
    """Bull — S&P 500 market scanner."""


@main.command()
@click.option(
    "--mode",
    type=click.Choice([m.value for m in ScanMode], case_sensitive=False),
    default=ScanMode.ALL.value,
    show_default=True,
    help="Scan mode: bullish | bearish | neutral | all",
)
@click.option(
    "--output",
    type=click.Choice([o.value for o in OutputFormat], case_sensitive=False),
    default=OutputFormat.CONSOLE.value,
    show_default=True,
    help="Output format.",
)
@click.option(
    "--out-file",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="Write JSON output to this file (only used when --output json).",
)
@click.option(
    "--universe",
    type=click.Choice([u.value for u in Universe], case_sensitive=False),
    default=Universe.SP500.value,
    show_default=True,
    help="Ticker universe: sp500 | nasdaq100 | dow30 | etf | mutual_fund | all",
)
@click.option(
    "--tickers",
    type=str,
    default=None,
    help="Comma-separated tickers (overrides --universe).",
)
@click.option(
    "--concurrency",
    type=click.IntRange(1, 50),
    default=None,
    help="Number of concurrent fetch threads.",
)
@click.option("-v", "--verbose", is_flag=True, default=False, help="Enable debug logging.")
def scan(
    mode: str,
    output: str,
    out_file: Path | None,
    universe: str,
    tickers: str | None,
    concurrency: int | None,
    verbose: bool,
) -> None:
    """
    Scan a ticker universe and report trading signals.

    \b
    Examples:
      bull scan
      bull scan --universe nasdaq100
      bull scan --universe etf --mode bearish
      bull scan --universe mutual_fund --mode all
      bull scan --universe all --mode bullish
      bull scan --tickers AAPL,MSFT,NVDA
    """
    _configure_logging(verbose)

    # Lazy imports so startup is fast for --help
    from bull.data.tickers import get_tickers_for_universe
    from bull.scanner import run_all_modes, run_scan

    # --tickers overrides --universe
    ticker_list: list[str] | None = None
    if tickers:
        ticker_list = [t.strip().upper() for t in tickers.split(",") if t.strip()]
    else:
        ticker_list = get_tickers_for_universe(universe)
        log.info("Universe '%s': %d tickers loaded.", universe, len(ticker_list))

    scan_mode = ScanMode(mode)
    output_format = OutputFormat(output)

    # ── Run scan ─────────────────────────────────────────────────────────────
    if scan_mode == ScanMode.ALL:
        results = run_all_modes(tickers=ticker_list, concurrency=concurrency)
    else:
        results = [run_scan(scan_mode, tickers=ticker_list, concurrency=concurrency)]

    # ── Report ───────────────────────────────────────────────────────────────
    _report(results, output_format, out_file)


def _report(results: list, output_format: OutputFormat, out_file: Path | None) -> None:
    if output_format == OutputFormat.CONSOLE:
        from bull.reporters.console import ConsoleReporter
        reporter = ConsoleReporter()
        for result in results:
            reporter.render(result)

    elif output_format == OutputFormat.JSON:
        from bull.reporters.json_report import JsonReporter
        import json
        import dataclasses
        import math

        def _serialise(obj):  # noqa: ANN001
            import datetime
            if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
                return {k: _serialise(v) for k, v in dataclasses.asdict(obj).items()}
            if isinstance(obj, (list, tuple)):
                return [_serialise(i) for i in obj]
            if isinstance(obj, dict):
                return {k: _serialise(v) for k, v in obj.items()}
            if isinstance(obj, (datetime.date, datetime.datetime)):
                return obj.isoformat()
            if isinstance(obj, float) and math.isnan(obj):
                return None
            return obj

        payload = [_serialise(r) for r in results]
        text = json.dumps(payload, indent=2)
        if out_file:
            out_file.write_text(text, encoding="utf-8")
            click.echo(f"Results written to {out_file}", err=True)
        else:
            click.echo(text)

    elif output_format == OutputFormat.EMAIL:
        from bull.reporters.email import EmailReporter
        reporter = EmailReporter()
        for result in results:
            reporter.render(result)
        click.echo("Email(s) sent.", err=True)
