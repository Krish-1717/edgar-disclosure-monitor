"""
alert_dispatcher.py — Multi-channel alert dispatch for EDGAR filing events.

Dispatches alerts via email (smtplib), Slack webhook, and generic HTTP webhook.
Includes rate limiting, exponential-backoff retry, and SQLite dispatch history.

Usage:
    dispatcher = AlertDispatcher()
    dispatcher.add_channel(SlackChannel(webhook_url="https://hooks.slack.com/..."))
    dispatcher.dispatch(alert)
"""

from __future__ import annotations

import json
import smtplib
import sqlite3
import time
import urllib.request
import urllib.error
from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Alert model
# ---------------------------------------------------------------------------

@dataclass
class Alert:
    alert_id: str
    ticker: str
    form_type: str         # 10-K, 8-K, etc.
    summary: str
    score: float           # 0-1 severity
    filing_date: str
    filing_url: str = ""
    priority: str = "MEDIUM"  # CRITICAL HIGH MEDIUM LOW
    tickers_mentioned: list = None

    def __post_init__(self):
        if self.tickers_mentioned is None:
            self.tickers_mentioned = [self.ticker]

    def to_text(self) -> str:
        return (
            f"[{self.priority}] {self.ticker} — {self.form_type}\n"
            f"Score: {self.score:.2f} | Filed: {self.filing_date}\n"
            f"{self.summary}\n"
            f"{self.filing_url}"
        )

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Dispatch result
# ---------------------------------------------------------------------------

@dataclass
class DispatchResult:
    channel_name: str
    success: bool
    attempts: int
    error: str = ""
    dispatched_at: str = ""


# ---------------------------------------------------------------------------
# Base channel
# ---------------------------------------------------------------------------

class Channel(ABC):
    name: str = "base"
    max_retries: int = 3
    retry_delay_s: float = 2.0

    @abstractmethod
    def _send(self, alert: Alert) -> None:
        """Send the alert. Raise on failure."""

    def send(self, alert: Alert) -> DispatchResult:
        last_err = ""
        for attempt in range(1, self.max_retries + 1):
            try:
                self._send(alert)
                return DispatchResult(
                    channel_name=self.name,
                    success=True,
                    attempts=attempt,
                    dispatched_at=datetime.utcnow().isoformat(),
                )
            except Exception as exc:
                last_err = str(exc)
                if attempt < self.max_retries:
                    time.sleep(self.retry_delay_s * (2 ** (attempt - 1)))
        return DispatchResult(
            channel_name=self.name,
            success=False,
            attempts=self.max_retries,
            error=last_err,
            dispatched_at=datetime.utcnow().isoformat(),
        )


# ---------------------------------------------------------------------------
# Email channel
# ---------------------------------------------------------------------------

@dataclass
class EmailConfig:
    smtp_host: str
    smtp_port: int
    username: str
    password: str
    from_addr: str
    to_addrs: list
    use_tls: bool = True


class EmailChannel(Channel):
    name = "email"

    def __init__(self, config: EmailConfig, min_score: float = 0.0):
        self.config = config
        self.min_score = min_score

    def _send(self, alert: Alert) -> None:
        if alert.score < self.min_score:
            return
        cfg = self.config
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"[EDGAR Alert] {alert.ticker} {alert.form_type} — score {alert.score:.2f}"
        msg["From"] = cfg.from_addr
        msg["To"] = ", ".join(cfg.to_addrs)

        body_text = alert.to_text()
        body_html = f"""
        <html><body style="font-family:sans-serif;background:#0d1117;color:#e6edf3;padding:20px">
        <h2 style="color:#f0883e">[{alert.priority}] {alert.ticker} — {alert.form_type}</h2>
        <p><b>Risk Score:</b> {alert.score:.2f} &nbsp; <b>Filed:</b> {alert.filing_date}</p>
        <p>{alert.summary}</p>
        <p><a href="{alert.filing_url}" style="color:#58a6ff">View Filing →</a></p>
        </body></html>
        """
        msg.attach(MIMEText(body_text, "plain"))
        msg.attach(MIMEText(body_html, "html"))

        if cfg.use_tls:
            with smtplib.SMTP(cfg.smtp_host, cfg.smtp_port) as server:
                server.starttls()
                server.login(cfg.username, cfg.password)
                server.sendmail(cfg.from_addr, cfg.to_addrs, msg.as_string())
        else:
            with smtplib.SMTP_SSL(cfg.smtp_host, cfg.smtp_port) as server:
                server.login(cfg.username, cfg.password)
                server.sendmail(cfg.from_addr, cfg.to_addrs, msg.as_string())


# ---------------------------------------------------------------------------
# Slack webhook channel
# ---------------------------------------------------------------------------

class SlackChannel(Channel):
    name = "slack"

    def __init__(self, webhook_url: str, min_score: float = 0.0,
                 mention_channel: bool = False):
        self.webhook_url = webhook_url
        self.min_score = min_score
        self.mention_channel = mention_channel

    def _send(self, alert: Alert) -> None:
        if alert.score < self.min_score:
            return
        color_map = {"CRITICAL": "#da3633", "HIGH": "#f0883e",
                     "MEDIUM": "#e3b341", "LOW": "#58a6ff"}
        color = color_map.get(alert.priority, "#8b949e")
        prefix = "<!channel> " if self.mention_channel and alert.priority == "CRITICAL" else ""
        payload = {
            "text": f"{prefix}EDGAR Filing Alert: *{alert.ticker}* {alert.form_type}",
            "attachments": [{
                "color": color,
                "fields": [
                    {"title": "Ticker", "value": alert.ticker, "short": True},
                    {"title": "Form", "value": alert.form_type, "short": True},
                    {"title": "Risk Score", "value": f"{alert.score:.2f}", "short": True},
                    {"title": "Priority", "value": alert.priority, "short": True},
                    {"title": "Filed", "value": alert.filing_date, "short": True},
                    {"title": "Summary", "value": alert.summary, "short": False},
                ],
                "actions": [{"type": "button", "text": "View Filing",
                              "url": alert.filing_url}] if alert.filing_url else [],
            }],
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self.webhook_url, data=data,
            headers={"Content-Type": "application/json"}, method="POST"
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status not in (200, 201):
                raise RuntimeError(f"Slack returned {resp.status}")


# ---------------------------------------------------------------------------
# Generic HTTP webhook channel
# ---------------------------------------------------------------------------

class WebhookChannel(Channel):
    name = "webhook"

    def __init__(self, url: str, headers: Optional[dict] = None,
                 min_score: float = 0.0):
        self.url = url
        self.headers = headers or {"Content-Type": "application/json"}
        self.min_score = min_score

    def _send(self, alert: Alert) -> None:
        if alert.score < self.min_score:
            return
        data = json.dumps(alert.to_dict()).encode("utf-8")
        req = urllib.request.Request(
            self.url, data=data, headers=self.headers, method="POST"
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status not in (200, 201, 202, 204):
                raise RuntimeError(f"Webhook returned {resp.status}")


# ---------------------------------------------------------------------------
# Rate limiter
# ---------------------------------------------------------------------------

class RateLimiter:
    """Token-bucket rate limiter: max_calls per window_seconds."""

    def __init__(self, max_calls: int = 10, window_seconds: float = 60.0):
        self.max_calls = max_calls
        self.window = window_seconds
        self._calls: list = []

    def acquire(self) -> bool:
        now = time.monotonic()
        self._calls = [t for t in self._calls if now - t < self.window]
        if len(self._calls) >= self.max_calls:
            return False
        self._calls.append(now)
        return True

    def wait_and_acquire(self) -> None:
        while not self.acquire():
            time.sleep(0.5)


# ---------------------------------------------------------------------------
# Alert Dispatcher
# ---------------------------------------------------------------------------

class AlertDispatcher:
    """
    Central dispatcher that routes alerts to all registered channels,
    records history in SQLite, and enforces rate limits.

    Usage:
        dispatcher = AlertDispatcher()
        dispatcher.add_channel(SlackChannel(webhook_url="..."))
        results = dispatcher.dispatch(alert)
    """

    def __init__(
        self,
        db_path: Path = Path("data/dispatch_history.db"),
        rate_limit: RateLimiter = None,
    ):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._channels: list = []
        self.rate_limiter = rate_limit or RateLimiter(max_calls=30, window_seconds=60)
        self._init_db()

    def _init_db(self) -> None:
        with self._conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS dispatch_history (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    alert_id     TEXT,
                    ticker       TEXT,
                    channel      TEXT,
                    success      INTEGER,
                    attempts     INTEGER,
                    error        TEXT,
                    dispatched_at TEXT
                )
            """)

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def add_channel(self, channel: Channel) -> None:
        self._channels.append(channel)

    def remove_channel(self, name: str) -> None:
        self._channels = [c for c in self._channels if c.name != name]

    def dispatch(self, alert: Alert) -> list:
        """Send alert to all channels. Returns list of DispatchResult."""
        self.rate_limiter.wait_and_acquire()
        results = []
        for channel in self._channels:
            result = channel.send(alert)
            results.append(result)
            self._record(alert, result)
        return results

    def dispatch_batch(self, alerts: list) -> dict:
        """Dispatch multiple alerts. Returns {alert_id: [DispatchResult]}."""
        return {a.alert_id: self.dispatch(a) for a in alerts}

    def _record(self, alert: Alert, result: DispatchResult) -> None:
        with self._conn() as conn:
            conn.execute(
                """INSERT INTO dispatch_history
                   (alert_id, ticker, channel, success, attempts, error, dispatched_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (alert.alert_id, alert.ticker, result.channel_name,
                 int(result.success), result.attempts, result.error,
                 result.dispatched_at),
            )

    def get_history(self, limit: int = 100) -> list:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM dispatch_history ORDER BY dispatched_at DESC LIMIT ?",
                (limit,)
            ).fetchall()
        return [dict(zip([d[0] for d in conn.execute("PRAGMA table_info(dispatch_history)").fetchall()], r))
                for r in rows]

    def success_rate(self) -> dict:
        with self._conn() as conn:
            rows = conn.execute("""
                SELECT channel, 
                       COUNT(*) as total,
                       SUM(success) as successes
                FROM dispatch_history GROUP BY channel
            """).fetchall()
        return {r[0]: {"total": r[1], "successes": r[2],
                        "rate": round(r[2]/r[1]*100, 1) if r[1] else 0}
                for r in rows}


if __name__ == "__main__":
    dispatcher = AlertDispatcher()
    # In real use, add configured channels:
    # dispatcher.add_channel(SlackChannel("https://hooks.slack.com/..."))
    sample = Alert(
        alert_id="demo_001",
        ticker="NVDA",
        form_type="8-K",
        summary="Nvidia discloses material supply chain disruption",
        score=0.85,
        filing_date="2026-10-01",
        filing_url="https://sec.gov/...",
        priority="HIGH",
    )
    print(f"Alert ready: {sample.to_text()}")
    print("No channels configured in demo — add SlackChannel/EmailChannel/WebhookChannel to send.")
