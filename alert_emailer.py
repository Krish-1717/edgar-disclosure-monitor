"""
alert_emailer.py — Email Digest for EDGAR Disclosure Monitor

Sends HTML email digests of CRITICAL and HIGH alerts to configured recipients.
Supports both SMTP (direct) and Resend API (recommended for production).

Configuration via environment variables:
  EMAIL_FROM       : sender address (e.g. "alerts@edgar-monitor.io")
  EMAIL_TO         : comma-separated recipient list
  SMTP_HOST        : SMTP server hostname (e.g. "smtp.gmail.com")
  SMTP_PORT        : SMTP port (default 587)
  SMTP_USER        : SMTP username
  SMTP_PASSWORD    : SMTP password / app password
  RESEND_API_KEY   : if set, uses Resend instead of SMTP

Usage:
    python alert_emailer.py                 # send digest for today's alerts
    python alert_emailer.py --min-rank 4    # only CRITICAL+HIGH
    python alert_emailer.py --dry-run       # print email without sending
"""
from __future__ import annotations
import argparse
import json
import logging
import os
import smtplib
import sqlite3
from datetime import date, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

log = logging.getLogger(__name__)

# ── Config ─────────────────────────────────────────────────────────────────────
EMAIL_FROM       = os.getenv("EMAIL_FROM", "alerts@edgar-monitor.io")
EMAIL_TO_RAW     = os.getenv("EMAIL_TO", "")
EMAIL_TO         = [e.strip() for e in EMAIL_TO_RAW.split(",") if e.strip()]
SMTP_HOST        = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT        = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER        = os.getenv("SMTP_USER", "")
SMTP_PASSWORD    = os.getenv("SMTP_PASSWORD", "")
RESEND_API_KEY   = os.getenv("RESEND_API_KEY", "")

RANK_LABELS = {5: "🔴 CRITICAL", 4: "🟠 HIGH", 3: "🟡 MEDIUM", 2: "🔵 LOW", 1: "⚪ MINIMAL"}
RANK_COLORS = {5: "#ef5350", 4: "#ffa726", 3: "#ffee58", 2: "#26c6da", 1: "#9e9e9e"}


# ── HTML Template ──────────────────────────────────────────────────────────────

def _alert_card_html(alert: sqlite3.Row) -> str:
    rank       = alert["ranking"]
    color      = RANK_COLORS.get(rank, "#9e9e9e")
    label      = RANK_LABELS.get(rank, "—")
    summary    = json.loads(alert.get("summary_items") or "[]")
    top_items  = ", ".join(f"Item {s['item']}" for s in summary[:3]) or "—"

    return f"""
<div style="background:#1e1e1e;border:1px solid #333;border-left:4px solid {color};
            border-radius:8px;padding:16px 20px;margin:12px 0;font-family:monospace">
  <div style="display:flex;justify-content:space-between;align-items:center">
    <span style="font-size:1.1em;font-weight:700;color:#fff">
      {alert['ticker']} — {alert.get('form','10-K/Q')}
    </span>
    <span style="background:{color}22;color:{color};border:1px solid {color}44;
                 border-radius:4px;padding:3px 10px;font-size:0.82em;font-weight:700">
      {label}
    </span>
  </div>
  <div style="color:#888;font-size:0.82em;margin:6px 0">
    Filed: {alert.get('filed','—')} &nbsp;|&nbsp; Period: {alert.get('period','—')}
  </div>
  <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin:10px 0">
    <div style="background:#111;border-radius:4px;padding:8px;text-align:center">
      <div style="color:#58a6ff;font-size:1.2em;font-weight:700">
        {round(alert.get('materiality_score',0),1)}
      </div>
      <div style="color:#666;font-size:0.72em">Materiality</div>
    </div>
    <div style="background:#111;border-radius:4px;padding:8px;text-align:center">
      <div style="color:{color};font-size:1.2em;font-weight:700">
        {round(alert.get('burial_score',0),1)}
      </div>
      <div style="color:#666;font-size:0.72em">Burial Score</div>
    </div>
    <div style="background:#111;border-radius:4px;padding:8px;text-align:center">
      <div style="color:#3fb950;font-size:1.2em;font-weight:700">
        {round(alert.get('attention_gap',0),1)}
      </div>
      <div style="color:#666;font-size:0.72em">Attention Gap</div>
    </div>
  </div>
  <div style="color:#aaa;font-size:0.82em">Top sections: {top_items}</div>
</div>
"""


def build_email_html(alerts: list[sqlite3.Row], report_date: str) -> str:
    """Build the full HTML digest email."""
    if not alerts:
        return ""

    critical_high = [a for a in alerts if a["ranking"] >= 4]
    other         = [a for a in alerts if a["ranking"] < 4]

    cards_ch = "".join(_alert_card_html(a) for a in critical_high)
    cards_ot = "".join(_alert_card_html(a) for a in other) if other else ""

    other_section = f"""
      <h2 style="color:#888;font-size:1em;margin:24px 0 8px">OTHER ALERTS</h2>
      {cards_ot}
    """ if other else ""

    return f"""
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="background:#0d1117;color:#e6edf3;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
             max-width:640px;margin:0 auto;padding:24px 16px">

  <div style="text-align:center;margin-bottom:28px">
    <div style="font-size:1.5em;font-weight:700;color:#fff">📋 EDGAR Disclosure Monitor</div>
    <div style="color:#8b949e;font-size:0.85em;margin-top:4px">Alert Digest — {report_date}</div>
  </div>

  <div style="background:#161b22;border:1px solid #30363d;border-radius:8px;
              padding:16px 20px;margin-bottom:20px;display:flex;gap:20px">
    <div style="text-align:center;flex:1">
      <div style="font-size:1.6em;font-weight:700;color:#ef5350">{len(critical_high)}</div>
      <div style="font-size:0.75em;color:#8b949e">Critical / High</div>
    </div>
    <div style="text-align:center;flex:1">
      <div style="font-size:1.6em;font-weight:700;color:#fff">{len(alerts)}</div>
      <div style="font-size:0.75em;color:#8b949e">Total Alerts</div>
    </div>
    <div style="text-align:center;flex:1">
      <div style="font-size:1.6em;font-weight:700;color:#58a6ff">
        {round(sum(a['attention_gap'] for a in alerts) / max(len(alerts),1), 1)}
      </div>
      <div style="font-size:0.75em;color:#8b949e">Avg Attention Gap</div>
    </div>
  </div>

  <h2 style="color:#ef5350;font-size:1em;margin:0 0 8px">🔴 CRITICAL / HIGH ALERTS</h2>
  {cards_ch if cards_ch else '<p style="color:#666;font-size:0.85em">None today.</p>'}

  {other_section}

  <div style="border-top:1px solid #21262d;margin-top:28px;padding-top:16px;
              text-align:center;color:#8b949e;font-size:0.75em">
    EDGAR Disclosure Monitor · github.com/Krish-1717/edgar-disclosure-monitor<br>
    You're receiving this because you're on the alert digest list.
  </div>
</body>
</html>
"""


# ── Sending ────────────────────────────────────────────────────────────────────

def send_via_smtp(subject: str, html: str, recipients: list[str]) -> bool:
    """Send HTML email via SMTP."""
    if not SMTP_USER or not SMTP_PASSWORD:
        log.error("SMTP_USER and SMTP_PASSWORD must be set")
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = EMAIL_FROM
    msg["To"]      = ", ".join(recipients)
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(EMAIL_FROM, recipients, msg.as_string())
        log.info("Email sent via SMTP to %d recipients", len(recipients))
        return True
    except Exception as e:
        log.error("SMTP error: %s", e)
        return False


def send_via_resend(subject: str, html: str, recipients: list[str]) -> bool:
    """Send HTML email via Resend API (https://resend.com)."""
    if not RESEND_API_KEY:
        log.error("RESEND_API_KEY not set")
        return False
    try:
        import requests
        resp = requests.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {RESEND_API_KEY}",
                "Content-Type":  "application/json",
            },
            json={
                "from":    EMAIL_FROM,
                "to":      recipients,
                "subject": subject,
                "html":    html,
            },
            timeout=15,
        )
        resp.raise_for_status()
        log.info("Email sent via Resend to %d recipients", len(recipients))
        return True
    except Exception as e:
        log.error("Resend error: %s", e)
        return False


def send_digest(
    conn: sqlite3.Connection,
    recipients: Optional[list[str]] = None,
    min_rank: int = 3,
    days_back: int = 1,
    dry_run: bool = False,
) -> bool:
    """
    Fetch recent alerts and send the digest email.

    Parameters
    ----------
    conn       : open DB connection
    recipients : email list; defaults to EMAIL_TO env var
    min_rank   : minimum alert rank to include (3=MEDIUM+)
    days_back  : how many days of alerts to include
    dry_run    : print HTML instead of sending
    """
    if recipients is None:
        recipients = EMAIL_TO

    cutoff = (date.today() - timedelta(days=days_back)).isoformat()
    alerts = conn.execute("""
        SELECT a.*, f.form
        FROM alerts a
        JOIN filings f ON a.new_filing_id = f.id
        WHERE a.ranking >= ?
          AND a.created_at >= ?
        ORDER BY a.attention_gap DESC
        LIMIT 50
    """, (min_rank, cutoff)).fetchall()

    if not alerts:
        log.info("No alerts (rank ≥ %d) in the last %d days — no email sent", min_rank, days_back)
        return True

    report_date = date.today().strftime("%B %d, %Y")
    subject     = f"EDGAR Monitor — {len(alerts)} alert{'s' if len(alerts)!=1 else ''} ({report_date})"
    html        = build_email_html(alerts, report_date)

    if dry_run:
        print(f"Subject: {subject}")
        print(f"To: {recipients}")
        print(f"\n[DRY RUN] Would send {len(html)} chars of HTML")
        print(f"  {len(alerts)} alerts (rank ≥ {min_rank})")
        return True

    if not recipients:
        log.error("No recipients — set EMAIL_TO env var")
        return False

    if RESEND_API_KEY:
        return send_via_resend(subject, html, recipients)
    elif SMTP_USER:
        return send_via_smtp(subject, html, recipients)
    else:
        log.error("No email transport configured. Set RESEND_API_KEY or SMTP_USER/SMTP_PASSWORD.")
        return False


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description="Send EDGAR alert digest email")
    parser.add_argument("--min-rank", type=int, default=4, help="Min alert rank (1-5)")
    parser.add_argument("--days-back", type=int, default=1, help="Days of history to include")
    parser.add_argument("--to", help="Comma-separated recipient emails")
    parser.add_argument("--dry-run", action="store_true", help="Print instead of sending")
    args = parser.parse_args()

    from database import get_connection, init_db
    conn = get_connection()
    init_db(conn)

    recipients = [e.strip() for e in args.to.split(",")] if args.to else None
    send_digest(conn, recipients=recipients, min_rank=args.min_rank,
                days_back=args.days_back, dry_run=args.dry_run)
