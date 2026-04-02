"""
HTML email reporter — extends Chris' email format with multi-mode support.

Sends an HTML email via Gmail SMTP when ``BULL_GMAIL_ADDRESS`` and
``BULL_GMAIL_APP_PASSWORD`` are configured.
"""

from __future__ import annotations

import logging
import smtplib
from datetime import date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from jinja2 import Environment, PackageLoader, select_autoescape

from bull.config import settings
from bull.exceptions import ConfigError, ReportError
from bull.models.signal import ScanResult

log = logging.getLogger(__name__)

# ── Jinja2 inline template (avoids needing a templates/ directory) ────────────

_HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<style>
  body { font-family: Arial, sans-serif; max-width: 960px; margin: 0 auto; background:#f5f5f5; }
  .header { padding: 16px; border-radius: 8px; color: white; margin-bottom: 16px; }
  .bullish  .header { background: #388E3C; }
  .bearish  .header { background: #C62828; }
  .neutral  .header { background: #F57F17; }
  .signal { border: 2px solid #ddd; margin: 14px 0; padding: 14px;
            border-radius: 8px; background: #fff; }
  .score-high  { border-color: #FFD700; background: #FFFDE7; }
  .score-med   { border-color: #90CAF9; background: #E3F2FD; }
  .score-low   { border-color: #A5D6A7; background: #E8F5E9; }
  .company-info{ background:#f0f0f0; padding:8px; border-radius:5px;
                 font-size:13px; margin:8px 0; }
  .metrics { display:grid; grid-template-columns:1fr 1fr 1fr; gap:8px; margin:10px 0; font-size:13px; }
  .metric  { background:#fff; padding:6px; border-radius:4px; border:1px solid #eee; }
  .metric-label { font-weight:bold; color:#666; font-size:11px; }
  .metric-value { color:#333; font-size:15px; }
  .targets  { background:#E8F5E9; padding:10px; border-radius:5px; margin:10px 0; }
  .bearish-targets { background:#FFEBEE; }
  .options  { background:#E3F2FD; padding:10px; border-radius:5px; margin:10px 0; font-size:13px; }
  .rationale{ background:#FFF9C4; padding:10px; border-radius:5px; margin:10px 0; font-size:13px; }
  .stars    { color:#FFD700; font-size:20px; }
  .ticker   { font-size:22px; font-weight:bold; }
  .badge    { display:inline-block; background:#666; color:white;
              padding:2px 8px; border-radius:3px; font-size:11px; margin-left:8px; }
  footer    { color:#888; font-size:11px; margin-top:20px; padding:12px;
              border-top:1px solid #ddd; }
</style>
</head>
<body class="{{ result.mode }}">
  <div class="header">
    <h1>{% if result.mode == 'bullish' %}📈{% elif result.mode == 'bearish' %}📉{% else %}⚖️{% endif %}
    Bull Scanner — {{ result.mode | capitalize }} Signals — {{ result.scan_date }}</h1>
    <p><strong>{{ result.total_signals }}</strong> signal(s) from
    <strong>{{ result.total_scanned }}</strong> tickers scanned</p>
    {% if result.sector_summary %}
    <p>Sectors: {% for s, c in result.sector_summary.items() %}{{ s }} ({{ c }}){% if not loop.last %}, {% endif %}{% endfor %}</p>
    {% endif %}
  </div>

  {% for sig in signals_sorted %}
  {% set score_class = 'score-high' if sig.score >= 6 else ('score-med' if sig.score >= 4 else 'score-low') %}
  <div class="signal {{ score_class }}">
    <span class="ticker">{{ sig.ticker }}</span>
    — {{ sig.company_name }}
    <span class="badge">{{ sig.sector }}</span>
    <span class="stars">{{ '★' * sig.stars }}{{ '☆' * (5 - sig.stars) }}</span>
    &nbsp;<small>Score {{ sig.score }}/10</small>

    <div class="company-info">{{ sig.description }}</div>

    <div class="metrics">
      <div class="metric"><div class="metric-label">CURRENT PRICE</div>
        <div class="metric-value">${{ "%.2f"|format(sig.current_price) }}</div></div>
      <div class="metric"><div class="metric-label">ATR-14</div>
        <div class="metric-value">${{ "%.2f"|format(sig.indicators.atr_14) }}</div></div>
      <div class="metric"><div class="metric-label">RSI-14</div>
        <div class="metric-value">{{ "%.1f"|format(sig.indicators.rsi_14) }}</div></div>
      <div class="metric"><div class="metric-label">VOLUME RATIO</div>
        <div class="metric-value">{{ "%.2f"|format(sig.indicators.volume_ratio) }}×</div></div>
      <div class="metric"><div class="metric-label">vs SMA-50</div>
        <div class="metric-value">{{ "%+.1f"|format(sig.indicators.distance_from_sma50) }}%</div></div>
      <div class="metric"><div class="metric-label">RISK / REWARD</div>
        <div class="metric-value">{{ "%.2f"|format(sig.risk_reward) }}:1</div></div>
    </div>

    <div class="targets {% if sig.mode == 'bearish' %}bearish-targets{% endif %}">
      <h3>🎯 Trade Plan</h3>
      <table><tr>
        <td><strong>Entry:</strong> ${{ "%.2f"|format(sig.entry_price) }}</td>
        <td style="padding:0 20px"><strong>Target (quick):</strong> ${{ "%.2f"|format(sig.target_quick) }}</td>
        <td><strong>{% if sig.mode == 'bearish' %}Cover{% else %}Extended{% endif %}:</strong>
            ${{ "%.2f"|format(sig.target_extended) }}</td>
        <td style="padding:0 20px"><strong>Stop:</strong> ${{ "%.2f"|format(sig.stop_loss) }}</td>
      </tr></table>
    </div>

    <div class="rationale">
      <strong>Why this signal:</strong><br>
      {% for line in sig.rationale %}&bull; {{ line }}<br>{% endfor %}
    </div>

    {% if sig.option_expirations %}
    <div class="options">
      <strong>📝 Options</strong> (exp: {{ sig.option_expirations | join(', ') }})<br>
      ITM ${{ "%.2f"|format(sig.suggested_strikes.ITM) }} &nbsp;
      <strong>★ ATM ${{ "%.2f"|format(sig.suggested_strikes.ATM) }}</strong> &nbsp;
      OTM ${{ "%.2f"|format(sig.suggested_strikes.OTM) }}<br>
      <small>Est. profit if target hit in 3–4 days: ~{{ sig.expected_option_profit_pct }}%</small>
    </div>
    {% endif %}
  </div>
  {% endfor %}

  <footer>
    <strong>Disclaimer:</strong> This is automated technical analysis for educational purposes only.
    Not financial advice. Always do your own due diligence.
  </footer>
</body>
</html>
"""


class EmailReporter:
    """Renders and sends an HTML email via Gmail SMTP."""

    def render(self, result: ScanResult) -> None:
        if not settings.email_configured:
            raise ConfigError(
                "Email credentials not configured. "
                "Set BULL_GMAIL_ADDRESS and BULL_GMAIL_APP_PASSWORD."
            )

        signals_sorted = sorted(result.signals, key=lambda s: s.score, reverse=True)
        html = _render_html(result, signals_sorted)
        subject = (
            f"Bull Scanner — {result.mode.capitalize()} — "
            f"{result.scan_date} ({result.total_signals} signals)"
        )
        _send(subject, html)

    def html_only(self, result: ScanResult) -> str:
        """Return rendered HTML without sending (useful for testing)."""
        signals_sorted = sorted(result.signals, key=lambda s: s.score, reverse=True)
        return _render_html(result, signals_sorted)


def _render_html(result: ScanResult, signals_sorted: list) -> str:
    from jinja2 import Environment

    env = Environment(autoescape=True)
    tmpl = env.from_string(_HTML_TEMPLATE)
    return tmpl.render(result=result, signals_sorted=signals_sorted)


def _send(subject: str, body_html: str) -> None:
    from_addr = settings.gmail_address
    password = settings.gmail_app_password
    to_addr = settings.effective_to_email or from_addr

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = from_addr
        msg["To"] = to_addr
        msg.attach(MIMEText(body_html, "html"))

        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(from_addr, password)
            server.send_message(msg)

        log.info("Email sent to %s", to_addr)
    except Exception as exc:
        raise ReportError(f"Failed to send email: {exc}") from exc
