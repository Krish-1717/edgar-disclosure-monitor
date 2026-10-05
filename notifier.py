"""
notifier.py — Multi-channel notification dispatcher for EDGAR Disclosure Monitor

Decision logic:
  - CRITICAL (attention_gap >= 80): all channels immediately (email + webhook + in-app)
  - HIGH     (attention_gap >= 60): email + in-app
  - MEDIUM   (attention_gap >= 40): in-app only
  - LOW      (attention_gap >= 20): in-app only (batched in daily digest)
  - Below 20: silently log, no notification

Deduplication: sent notifications are tracked in data/sent_notifications.json
keyed by "{ticker}:{accession}:{source}" — same alert never fires twice.
"""

from __future__ import annotations

import json
import logging
import os
import smtplib
import urllib.request
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class Notification:
    ticker: str
    title: str
    body: str
    severity: str           # CRITICAL / HIGH / MEDIUM / LOW
    source: str             # "SEC_FILING" | "NEWS" | "COMBINED"
    materiality_score: float
    news_quality_score: float
    attention_gap: float
    url: str
    filed_at: str
    sentiment: str
    top_bucket: str
    accession: str = ""     # SEC accession number for dedup key

    @property
    def dedup_key(self) -> str:
        return f"{self.ticker}:{self.accession}:{self.source}"


# ---------------------------------------------------------------------------
# HTML email template (dark theme matching the Bloomberg-style frontend)
# ---------------------------------------------------------------------------

_EMAIL_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<style>
  body{{background:#0a0f1a;color:#e2e8f0;font-family:system-ui,sans-serif;margin:0;padding:20px}}
  .card{{background:#0d1526;border:1px solid #1e3a5f;border-radius:8px;max-width:620px;margin:0 auto;padding:24px}}
  .header{{display:flex;align-items:center;gap:12px;border-bottom:1px solid #1e3a5f;padding-bottom:16px;margin-bottom:20px}}
  .badge{{background:{severity_color};color:#fff;padding:3px 10px;border-radius:4px;font-size:12px;font-weight:700}}
  .ticker{{color:#00d4ff;font-size:22px;font-weight:700}}
  .title{{color:#e2e8f0;font-size:16px;margin:0 0 12px}}
  .body{{color:#94a3b8;font-size:14px;line-height:1.6;margin:0 0 20px}}
  .meta-row{{display:flex;gap:20px;flex-wrap:wrap;font-size:12px;color:#64748b;margin-bottom:20px}}
  .meta-item span{{color:#94a3b8;font-weight:600}}
  .cta{{display:inline-block;background:#1e40af;color:#fff;padding:10px 20px;border-radius:6px;text-decoration:none;font-weight:600;font-size:14px}}
  .footer{{border-top:1px solid #1e3a5f;margin-top:20px;padding-top:16px;font-size:11px;color:#475569}}
  .gap-bar{{background:#1e3a5f;border-radius:4px;height:8px;overflow:hidden;margin:8px 0}}
  .gap-fill{{background:{severity_color};height:8px;border-radius:4px;width:{gap_pct}%}}
</style>
</head>
<body>
<div class="card">
  <div class="header">
    <span class="ticker">{ticker}</span>
    <span class="badge">{severity}</span>
    <span style="color:#64748b;font-size:13px">{source}</span>
  </div>
  <h2 class="title">{title}</h2>
  <p class="body">{body}</p>
  <div class="meta-row">
    <div class="meta-item">Attention Gap<br/><span>{attention_gap:.1f}</span></div>
    <div class="meta-item">Materiality<br/><span>{materiality_score:.2f}</span></div>
    <div class="meta-item">News Quality<br/><span>{news_quality_score:.2f}</span></div>
    <div class="meta-item">Sentiment<br/><span>{sentiment}</span></div>
    <div class="meta-item">Signal Bucket<br/><span>{top_bucket}</span></div>
    <div class="meta-item">Filed<br/><span>{filed_at}</span></div>
  </div>
  <div class="gap-bar"><div class="gap-fill"></div></div>
  <br/>
  <a class="cta" href="{url}">View Filing &#x2192;</a>
  <div class="footer">
    EDGAR Disclosure Monitor &middot; {timestamp} UTC<br/>
    You received this because this ticker is on your watchlist.
  </div>
</div>
</body>
</html>"""

_SEVERITY_COLORS = {
    "CRITICAL": "#dc2626",
    "HIGH":     "#d97706",
    "MEDIUM":   "#2563eb",
    "LOW":      "#16a34a",
}


def _build_html(notif: Notification) -> str:
    color = _SEVERITY_COLORS.get(notif.severity, "#64748b")
    gap_pct = min(100, notif.attention_gap)
    return _EMAIL_HTML.format(
        ticker=notif.ticker,
        severity=notif.severity,
        source=notif.source,
        title=notif.title,
        body=notif.body,
        attention_gap=notif.attention_gap,
        materiality_score=notif.materiality_score,
        news_quality_score=notif.news_quality_score,
        sentiment=notif.sentiment,
        top_bucket=notif.top_bucket,
        filed_at=notif.filed_at,
        url=notif.url,
        severity_color=color,
        gap_pct=gap_pct,
        timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"),
    )


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

class NotificationDispatcher:
    """Routes Notification objects to one or more channels based on severity.

    Config keys (all optional):
      smtp_host, smtp_port, smtp_user, smtp_pass  — email channel
      webhook_url                                  — Slack-compatible webhook
      email_recipients                             — list[str]
      thresholds.critical / high / medium / low   — attention_gap cutoffs
    """

    DEFAULT_THRESHOLDS = {"critical": 80, "high": 60, "medium": 40, "low": 20}

    def __init__(self, config: dict):
        self.config = config
        self.thresholds = {**self.DEFAULT_THRESHOLDS, **config.get("thresholds", {})}
        self._sent_path = Path(config.get("sent_notifications_path", "data/sent_notifications.json"))
        self._notif_path = Path(config.get("notifications_jsonl_path", "data/notifications.jsonl"))
        self._sent: dict = self._load_sent()

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------

    def _load_sent(self) -> dict:
        if self._sent_path.exists():
            try:
                return json.loads(self._sent_path.read_text())
            except Exception:
                return {}
        return {}

    def _save_sent(self) -> None:
        self._sent_path.parent.mkdir(parents=True, exist_ok=True)
        self._sent_path.write_text(json.dumps(self._sent, indent=2))

    def _is_duplicate(self, notif: Notification) -> bool:
        return notif.dedup_key in self._sent

    def _mark_sent(self, notif: Notification) -> None:
        self._sent[notif.dedup_key] = datetime.now(timezone.utc).isoformat()
        self._save_sent()

    # ------------------------------------------------------------------
    # Severity classification
    # ------------------------------------------------------------------

    def classify_severity(self, attention_gap: float) -> str:
        if attention_gap >= self.thresholds["critical"]:
            return "CRITICAL"
        if attention_gap >= self.thresholds["high"]:
            return "HIGH"
        if attention_gap >= self.thresholds["medium"]:
            return "MEDIUM"
        if attention_gap >= self.thresholds["low"]:
            return "LOW"
        return "SILENT"

    # ------------------------------------------------------------------
    # Channel: email
    # ------------------------------------------------------------------

    def send_email(self, notif: Notification, recipients: list) -> bool:
        """Send an HTML email via SMTP. Reads credentials from config or env vars."""
        host = self.config.get("smtp_host") or os.environ.get("SMTP_HOST", "localhost")
        port = int(self.config.get("smtp_port") or os.environ.get("SMTP_PORT", 587))
        user = self.config.get("smtp_user") or os.environ.get("SMTP_USER", "")
        pw   = self.config.get("smtp_pass") or os.environ.get("SMTP_PASS", "")

        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"[{notif.severity}] {notif.ticker} — {notif.title}"
        msg["From"]    = user or "noreply@edgar-monitor.local"
        msg["To"]      = ", ".join(recipients)

        plain = (f"{notif.title}\n\n{notif.body}\n\n"
                 f"Attention Gap: {notif.attention_gap:.1f}\n{notif.url}")
        msg.attach(MIMEText(plain, "plain"))
        msg.attach(MIMEText(_build_html(notif), "html"))

        try:
            with smtplib.SMTP(host, port, timeout=10) as server:
                server.ehlo()
                if port != 25:
                    server.starttls()
                if user and pw:
                    server.login(user, pw)
                server.sendmail(msg["From"], recipients, msg.as_string())
            logger.info("Email sent to %s for %s", recipients, notif.ticker)
            return True
        except Exception as exc:
            logger.error("Email failed: %s", exc)
            return False

    # ------------------------------------------------------------------
    # Channel: webhook (Slack-compatible)
    # ------------------------------------------------------------------

    def send_webhook(self, notif: Notification, webhook_url: str) -> bool:
        """POST a Slack-compatible JSON payload to webhook_url."""
        color = _SEVERITY_COLORS.get(notif.severity, "#64748b")
        payload = {
            "text": f"*[{notif.severity}] {notif.ticker}* — {notif.title}",
            "attachments": [
                {
                    "color": color,
                    "fields": [
                        {"title": "Source",        "value": notif.source,                     "short": True},
                        {"title": "Attention Gap", "value": f"{notif.attention_gap:.1f}",     "short": True},
                        {"title": "Materiality",   "value": f"{notif.materiality_score:.2f}", "short": True},
                        {"title": "Sentiment",     "value": notif.sentiment,                  "short": True},
                        {"title": "Top Signal",    "value": notif.top_bucket,                 "short": True},
                        {"title": "Filed At",      "value": notif.filed_at,                   "short": True},
                    ],
                    "text": notif.body,
                    "footer": "EDGAR Disclosure Monitor",
                    "ts": int(datetime.now(timezone.utc).timestamp()),
                    "actions": [{"type": "button", "text": "View Filing", "url": notif.url}],
                }
            ],
        }
        data = json.dumps(payload).encode()
        req  = urllib.request.Request(
            webhook_url, data=data,
            headers={"Content-Type": "application/json"}, method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                ok = resp.status < 300
            logger.info("Webhook %s for %s", "OK" if ok else "FAILED", notif.ticker)
            return ok
        except Exception as exc:
            logger.error("Webhook error: %s", exc)
            return False

    # ------------------------------------------------------------------
    # Channel: in-app (JSONL file polled by frontend)
    # ------------------------------------------------------------------

    def send_in_app(self, notif: Notification) -> None:
        """Append one JSON line to data/notifications.jsonl for the frontend to poll."""
        self._notif_path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            **asdict(notif),
            "ts": datetime.now(timezone.utc).isoformat(),
            "read": False,
        }
        with self._notif_path.open("a") as fh:
            fh.write(json.dumps(record) + "\n")
        logger.info("In-app notification written for %s", notif.ticker)

    # ------------------------------------------------------------------
    # Main dispatch
    # ------------------------------------------------------------------

    def dispatch(self, notif: Notification) -> Optional[str]:
        """Route notification to appropriate channels.

        Returns the severity string dispatched to, or None if silenced/duplicate.
        """
        severity = self.classify_severity(notif.attention_gap)
        notif.severity = severity

        if severity == "SILENT":
            logger.debug("Silenced %s (gap=%.1f)", notif.ticker, notif.attention_gap)
            return None

        if self._is_duplicate(notif):
            logger.info("Duplicate suppressed: %s", notif.dedup_key)
            return None

        recipients = self.config.get("email_recipients", [])
        webhook    = self.config.get("webhook_url", "")

        if severity == "CRITICAL":
            if recipients:
                self.send_email(notif, recipients)
            if webhook:
                self.send_webhook(notif, webhook)
            self.send_in_app(notif)

        elif severity == "HIGH":
            if recipients:
                self.send_email(notif, recipients)
            self.send_in_app(notif)

        elif severity in ("MEDIUM", "LOW"):
            self.send_in_app(notif)

        self._mark_sent(notif)
        logger.info("Dispatched %s alert for %s", severity, notif.ticker)
        return severity


# ---------------------------------------------------------------------------
# Config loader
# ---------------------------------------------------------------------------

def load_config(path: str = "config/notifier_config.json") -> dict:
    p = Path(path)
    if p.exists():
        return json.loads(p.read_text())
    return {
        "thresholds": {"critical": 80, "high": 60, "medium": 40, "low": 20},
        "email_recipients": [],
        "webhook_url": "",
    }


# ---------------------------------------------------------------------------
# Demo / CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    cfg = load_config()
    dispatcher = NotificationDispatcher(cfg)

    samples = [
        Notification(
            ticker="NVDA",
            title="NVDA files 10-K with 43-point attention gap vs analyst coverage",
            body=("NVIDIA's annual filing discloses AI chip export restriction risks "
                  "absent from 94% of analyst reports."),
            severity="", source="COMBINED",
            materiality_score=0.87, news_quality_score=0.71,
            attention_gap=85.0,
            url="https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=NVDA",
            filed_at="2026-10-05T09:00:00Z",
            sentiment="BEARISH", top_bucket="REGULATORY",
            accession="0001045810-26-000012",
        ),
        Notification(
            ticker="AAPL",
            title="Apple Q3 10-Q filed",
            body="Quarterly filing shows services revenue growth slowing.",
            severity="", source="SEC_FILING",
            materiality_score=0.42, news_quality_score=0.52,
            attention_gap=35.0,
            url="https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=AAPL",
            filed_at="2026-10-05T08:30:00Z",
            sentiment="NEUTRAL", top_bucket="EARNINGS",
            accession="0000320193-26-000099",
        ),
        Notification(
            ticker="JPM",
            title="JPM 10-K regulatory risk disclosure",
            body="Basel III capital requirements discussed in risk factors.",
            severity="", source="SEC_FILING",
            materiality_score=0.65, news_quality_score=0.68,
            attention_gap=62.0,
            url="https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=JPM",
            filed_at="2026-10-05T07:00:00Z",
            sentiment="BEARISH", top_bucket="REGULATORY",
            accession="0000019617-26-000055",
        ),
    ]

    print("=" * 60)
    print("NotificationDispatcher demo")
    print("=" * 60)
    for s in samples:
        result = dispatcher.dispatch(s)
        print(f"  {s.ticker:6s}  gap={s.attention_gap:5.1f}  severity={s.severity:8s}  "
              f"→ dispatched as {result or 'SILENT'}")
    print("\nDuplicate dedup test (re-dispatching same notifications):")
    for s in samples:
        result = dispatcher.dispatch(s)
        print(f"  {s.ticker:6s}  → {result or 'SUPPRESSED (duplicate)'}")
