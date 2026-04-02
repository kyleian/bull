"""
Rich terminal reporter.

Renders scan results as a coloured table in the terminal using the `rich`
library.  Bullish signals are green, bearish are red, neutral are yellow.
"""

from __future__ import annotations

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from bull.models.signal import ScanResult, Signal

_CONSOLE = Console()

_MODE_STYLE: dict[str, str] = {
    "bullish": "bold green",
    "bearish": "bold red",
    "neutral": "bold yellow",
}


class ConsoleReporter:
    """Renders a ``ScanResult`` to stdout using Rich."""

    def render(self, result: ScanResult) -> None:
        if not result.signals:
            _CONSOLE.print(
                Panel(
                    f"[dim]No {result.mode} signals found for {result.scan_date}.[/dim]",
                    title="Bull Scanner",
                )
            )
            return

        _CONSOLE.rule(f"[bold]Bull Scanner — {result.mode.upper()} — {result.scan_date}[/bold]")
        _CONSOLE.print(
            f"  Scanned: [cyan]{result.total_scanned}[/cyan]  "
            f"Signals: [bold]{result.total_signals}[/bold]  "
            f"Errors: [dim]{len(result.errors)}[/dim]\n"
        )

        # Top-level sector summary
        if result.sector_summary:
            _CONSOLE.print("[bold]Sector Breakdown:[/bold]")
            for sector, count in result.sector_summary.items():
                _CONSOLE.print(f"  {sector}: {count}")
            _CONSOLE.print()

        for sig in sorted(result.signals, key=lambda s: s.score, reverse=True):
            _render_signal(sig)

        if result.errors:
            _CONSOLE.rule("[dim]Skipped Tickers[/dim]")
            for ticker, reason in list(result.errors.items())[:20]:
                _CONSOLE.print(f"  [dim]{ticker}: {reason}[/dim]")


def _render_signal(sig: Signal) -> None:
    style = _MODE_STYLE.get(sig.mode, "white")

    tbl = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
    tbl.add_column("Key", style="dim", width=22)
    tbl.add_column("Value")

    tbl.add_row("Mode", Text(sig.mode.upper(), style=style))
    tbl.add_row("Rating", f"{sig.star_display}  ({sig.score:.1f}/10)")
    tbl.add_row("Sector", sig.sector)
    tbl.add_row("Current Price", f"${sig.current_price:.2f}")
    tbl.add_row("Entry", f"${sig.entry_price:.2f}")
    if sig.mode == "bearish":
        tbl.add_row("Target (Quick)", f"${sig.target_quick:.2f}  [dim](put target)[/dim]")
        tbl.add_row("Stop Loss", f"${sig.stop_loss:.2f}")
    else:
        tbl.add_row("Target (Quick)", f"${sig.target_quick:.2f}  [dim](+{_pct(sig.entry_price, sig.target_quick):.1f}%)[/dim]")
        tbl.add_row("Target (Ext.)", f"${sig.target_extended:.2f}")
        tbl.add_row("Stop Loss", f"${sig.stop_loss:.2f}  [dim](-{_pct(sig.entry_price, sig.stop_loss, invert=True):.1f}%)[/dim]")
    tbl.add_row("Risk/Reward", f"{sig.risk_reward:.2f}:1")
    tbl.add_row("ATR-14", f"${sig.indicators.atr_14:.2f}")
    tbl.add_row("Volume Ratio", f"{sig.indicators.volume_ratio:.2f}×")
    tbl.add_row("RSI-14", f"{sig.indicators.rsi_14:.1f}")
    tbl.add_row("vs SMA-50", f"{sig.indicators.distance_from_sma50:+.1f}%")

    # Rationale bullets
    rationale_text = "\n".join(f"• {r}" for r in sig.rationale)

    # Options
    strikes = sig.suggested_strikes
    opt_text = (
        f"Expirations: {', '.join(sig.option_expirations)}  |  "
        f"ITM ${strikes.get('ITM', 0):.2f}  ATM ${strikes.get('ATM', 0):.2f}  OTM ${strikes.get('OTM', 0):.2f}  "
        f"| Est. option profit if target hit: ~{sig.expected_option_profit_pct:.0f}%"
    )

    _CONSOLE.print(
        Panel(
            f"[bold]{sig.ticker}[/bold] — {sig.company_name}\n\n"
            f"[italic dim]{sig.description[:200]}[/italic dim]\n\n"
            + tbl.__rich_console__(_CONSOLE, _CONSOLE.options).__class__.__name__  # trick: just print it
            ,
            title=f"[{style}]{sig.ticker} — {sig.mode.upper()}[/{style}]",
        )
    )
    _CONSOLE.print(tbl)
    _CONSOLE.print(f"[bold]Why:[/bold]\n{rationale_text}")
    _CONSOLE.print(f"[dim]{opt_text}[/dim]")
    _CONSOLE.print()


def _pct(a: float, b: float, invert: bool = False) -> float:
    if a == 0:
        return 0.0
    return abs((b - a) / a) * 100 if not invert else abs((a - b) / a) * 100
