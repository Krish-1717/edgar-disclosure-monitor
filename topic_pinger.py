"""
topic_pinger.py — User topic & stock ping management.

Users "ping" topics they care about — a stock ticker, a geopolitical event,
a company name, an industry, or a free-text query like "war between Iran and USA".
The pinger stores these signals and routes incoming news + filings to the right users.

Features:
  - Free-text topic pings  ("Iran oil sanctions", "Fed rate hike")
  - Ticker pings           ("NVDA", "TSLA")
  - Industry pings         ("semiconductor", "banking")
  - Priority levels        (CRITICAL → breaks through; LOW → digest only)
  - Mute windows           (silence a topic for N hours)
  - Relevance threshold    (only fire if relevance score ≥ threshold)
  - Delivery channels      (email, webhook, in-app)
"""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DB_PATH = Path("data/pings.db")

PRIORITY_WEIGHTS = {
    "CRITICAL": 1.0,
    "HIGH":     0.75,
    "MEDIUM":   0.50,
    "LOW":      0.25,
}

DELIVERY_CHANNELS = {"email", "webhook", "in_app", "sms"}


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class Ping:
    ping_id: str            # slug from topic text
    user_id: str            # user or device identifier
    topic: str              # raw user input: "war between Iran and USA"
    keywords: list[str]     # extracted search terms
    tickers: list[str]      # associated tickers (if any)
    industry: str           # e.g. "energy", "semiconductors"
    priority: str           # CRITICAL | HIGH | MEDIUM | LOW
    min_relevance: float    # 0–1; only fire if score ≥ this
    channels: list[str]     # delivery methods
    muted_until: str        # ISO datetime or ""
    created_at: str
    last_fired_at: str
    fire_count: int
    is_active: bool


@dataclass
class PingMatch:
    ping: Ping
    relevance_score: float  # 0–1
    matched_keywords: list[str]
    matched_tickers: list[str]
    source_item_id: str     # article_id or accession number
    source_type: str        # "news" | "filing"
    fired_at: str


# ---------------------------------------------------------------------------
# Keyword extractor (no external NLP deps)
# ---------------------------------------------------------------------------

_STOP_WORDS = {
    "a","an","the","and","or","but","in","on","at","to","of","for","with",
    "is","are","was","were","be","been","has","have","had","this","that",
    "it","its","by","from","as","i","we","they","you","he","she","between",
    "about","into","than","so","not","will","can","may","would","should",
    "also","just","more","some","all","any","our","their","which","when",
    "there","up","out","over","after","before","during","while",
}

def extract_keywords(topic: str) -> list[str]:
    """
    Extract meaningful search keywords from a user topic string.
    "war between Iran and USA" → ["war", "iran", "usa"]
    "Federal Reserve rate hike semiconductor stocks" → ["federal", "reserve", "rate", "hike", "semiconductor"]
    """
    words = re.findall(r"\b[a-zA-Z]{2,}\b", topic.lower())
    keywords = [w for w in words if w not in _STOP_WORDS]
    # Also keep adjacent pairs (bigrams) for phrases
    bigrams = [f"{keywords[i]} {keywords[i+1]}" for i in range(len(keywords)-1)]
    return keywords + bigrams[:5]  # limit bigrams


def extract_tickers_from_topic(topic: str) -> list[str]:
    """Extract uppercase 1-5 letter tokens that look like tickers."""
    return re.findall(r"\b([A-Z]{1,5})\b", topic)


_INDUSTRY_MAP = {
    "tech":          ["technology", "software", "semiconductor", "ai", "cloud", "chip"],
    "energy":        ["energy", "oil", "gas", "petroleum", "lng", "opec", "refiner"],
    "finance":       ["bank", "financial", "fed", "rate", "credit", "lending", "insurance"],
    "healthcare":    ["pharma", "drug", "fda", "biotech", "clinical", "vaccine"],
    "defense":       ["defense", "military", "weapon", "war", "nato", "pentagon", "army"],
    "geopolitical":  ["iran", "china", "russia", "ukraine", "taiwan", "sanctions", "tariff"],
    "consumer":      ["retail", "consumer", "brand", "luxury", "fashion", "ecommerce"],
    "real_estate":   ["reit", "housing", "mortgage", "property", "commercial"],
    "commodities":   ["gold", "silver", "copper", "wheat", "corn", "commodity", "futures"],
}

def infer_industry(topic: str) -> str:
    t = topic.lower()
    for industry, keywords in _INDUSTRY_MAP.items():
        if any(kw in t for kw in keywords):
            return industry
    return "general"


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

class PingStore:
    def __init__(self, db_path: Path = DB_PATH):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._init()

    def _init(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS pings (
                ping_id       TEXT,
                user_id       TEXT,
                topic         TEXT,
                keywords      TEXT,
                tickers       TEXT,
                industry      TEXT,
                priority      TEXT,
                min_relevance REAL,
                channels      TEXT,
                muted_until   TEXT,
                created_at    TEXT,
                last_fired_at TEXT,
                fire_count    INTEGER DEFAULT 0,
                is_active     INTEGER DEFAULT 1,
                PRIMARY KEY (ping_id, user_id)
            );
            CREATE TABLE IF NOT EXISTS ping_history (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                ping_id       TEXT,
                user_id       TEXT,
                source_item_id TEXT,
                source_type   TEXT,
                relevance     REAL,
                fired_at      TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_ping_user ON pings(user_id);
            CREATE INDEX IF NOT EXISTS idx_ping_active ON pings(is_active);
        """)
        self.conn.commit()

    def save_ping(self, p: Ping):
        self.conn.execute("""
            INSERT OR REPLACE INTO pings
            (ping_id, user_id, topic, keywords, tickers, industry, priority,
             min_relevance, channels, muted_until, created_at, last_fired_at,
             fire_count, is_active)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            p.ping_id, p.user_id, p.topic,
            json.dumps(p.keywords), json.dumps(p.tickers),
            p.industry, p.priority, p.min_relevance,
            json.dumps(p.channels), p.muted_until,
            p.created_at, p.last_fired_at, p.fire_count, int(p.is_active),
        ))
        self.conn.commit()

    def get_active_pings(self, user_id: str = "") -> list[Ping]:
        if user_id:
            cur = self.conn.execute(
                "SELECT * FROM pings WHERE is_active=1 AND user_id=?", (user_id,))
        else:
            cur = self.conn.execute("SELECT * FROM pings WHERE is_active=1")
        return [self._row_to_ping(r) for r in cur.fetchall()]

    def get_all_pings(self, user_id: str = "") -> list[Ping]:
        if user_id:
            cur = self.conn.execute("SELECT * FROM pings WHERE user_id=?", (user_id,))
        else:
            cur = self.conn.execute("SELECT * FROM pings")
        return [self._row_to_ping(r) for r in cur.fetchall()]

    def deactivate(self, ping_id: str, user_id: str):
        self.conn.execute(
            "UPDATE pings SET is_active=0 WHERE ping_id=? AND user_id=?",
            (ping_id, user_id))
        self.conn.commit()

    def mute(self, ping_id: str, user_id: str, hours: int = 24):
        until = (datetime.utcnow() + timedelta(hours=hours)).isoformat()
        self.conn.execute(
            "UPDATE pings SET muted_until=? WHERE ping_id=? AND user_id=?",
            (until, ping_id, user_id))
        self.conn.commit()

    def record_fire(self, match: PingMatch):
        self.conn.execute("""
            INSERT INTO ping_history (ping_id, user_id, source_item_id, source_type, relevance, fired_at)
            VALUES (?,?,?,?,?,?)
        """, (match.ping.ping_id, match.ping.user_id, match.source_item_id,
              match.source_type, match.relevance_score, match.fired_at))
        self.conn.execute("""
            UPDATE pings SET last_fired_at=?, fire_count=fire_count+1
            WHERE ping_id=? AND user_id=?
        """, (match.fired_at, match.ping.ping_id, match.ping.user_id))
        self.conn.commit()

    def _row_to_ping(self, row) -> Ping:
        cols = ["ping_id","user_id","topic","keywords","tickers","industry",
                "priority","min_relevance","channels","muted_until",
                "created_at","last_fired_at","fire_count","is_active"]
        d = dict(zip(cols, row))
        return Ping(
            ping_id=d["ping_id"], user_id=d["user_id"], topic=d["topic"],
            keywords=json.loads(d["keywords"] or "[]"),
            tickers=json.loads(d["tickers"] or "[]"),
            industry=d["industry"], priority=d["priority"],
            min_relevance=d["min_relevance"],
            channels=json.loads(d["channels"] or '["in_app"]'),
            muted_until=d["muted_until"] or "",
            created_at=d["created_at"], last_fired_at=d["last_fired_at"] or "",
            fire_count=int(d["fire_count"] or 0),
            is_active=bool(d["is_active"]),
        )


# ---------------------------------------------------------------------------
# Ping manager
# ---------------------------------------------------------------------------

class TopicPinger:
    """
    Manages user topic pings and matches them against incoming content.

    Example usage:
        pinger = TopicPinger(user_id="user_1")
        # Add pings
        pinger.ping("war between Iran and USA", priority="HIGH")
        pinger.ping("NVDA earnings miss", priority="CRITICAL", tickers=["NVDA"])
        pinger.ping("Federal Reserve rate decision")

        # Match against an incoming news article
        article = {"title": "Iran threatens Strait of Hormuz closure", ...}
        matches = pinger.match_content(article, source_type="news")

        # List active pings
        for p in pinger.list_pings():
            print(p.topic, p.priority)

        # Mute a noisy ping for 12 hours
        pinger.mute("iran-usa", hours=12)
    """

    def __init__(self, user_id: str = "default", db_path: Path = DB_PATH):
        self.user_id = user_id
        self.store = PingStore(db_path)

    def ping(
        self,
        topic: str,
        priority: str = "HIGH",
        tickers: list[str] = None,
        min_relevance: float = 0.35,
        channels: list[str] = None,
    ) -> Ping:
        """
        Create a new topic ping.

        Args:
            topic: Free-text topic description, e.g. "war between Iran and USA"
            priority: CRITICAL | HIGH | MEDIUM | LOW
            tickers: Optional list of associated tickers
            min_relevance: Minimum relevance score (0–1) to fire the ping
            channels: Delivery channels (default: in_app)

        Returns:
            Created Ping object.
        """
        keywords = extract_keywords(topic)
        auto_tickers = extract_tickers_from_topic(topic)
        all_tickers = list(set((tickers or []) + auto_tickers))
        industry = infer_industry(topic)
        ping_id = re.sub(r"[^a-z0-9]+", "-", topic.lower())[:40].strip("-")

        p = Ping(
            ping_id=ping_id,
            user_id=self.user_id,
            topic=topic,
            keywords=keywords,
            tickers=all_tickers,
            industry=industry,
            priority=priority.upper(),
            min_relevance=min_relevance,
            channels=channels or ["in_app"],
            muted_until="",
            created_at=datetime.utcnow().isoformat(),
            last_fired_at="",
            fire_count=0,
            is_active=True,
        )
        self.store.save_ping(p)
        return p

    def remove(self, topic_substring: str):
        """Deactivate pings whose topic contains the given substring."""
        for p in self.store.get_active_pings(self.user_id):
            if topic_substring.lower() in p.topic.lower():
                self.store.deactivate(p.ping_id, self.user_id)

    def mute(self, topic_substring: str, hours: int = 24):
        """Mute matching pings for N hours."""
        for p in self.store.get_active_pings(self.user_id):
            if topic_substring.lower() in p.topic.lower():
                self.store.mute(p.ping_id, self.user_id, hours)

    def list_pings(self) -> list[Ping]:
        return self.store.get_active_pings(self.user_id)

    def match_content(
        self,
        content: dict,
        source_type: str = "news",
    ) -> list[PingMatch]:
        """
        Match a content item (article dict or filing dict) against all active pings.

        content keys expected:
          news:    title, summary, full_text, tickers_mentioned
          filing:  company_name, ticker, form_type, period_of_report (+ text if available)

        Returns list of PingMatch objects where relevance ≥ ping.min_relevance
        and the ping is not muted.
        """
        text = " ".join(filter(None, [
            content.get("title", ""),
            content.get("summary", ""),
            content.get("full_text", "")[:3000],
            content.get("company_name", ""),
            content.get("form_type", ""),
        ])).lower()

        content_tickers = [t.upper() for t in (
            content.get("tickers_mentioned", []) +
            ([content.get("ticker")] if content.get("ticker") else [])
        )]

        now = datetime.utcnow()
        matches = []

        for ping in self.store.get_active_pings(self.user_id):
            # Check mute
            if ping.muted_until:
                try:
                    mute_dt = datetime.fromisoformat(ping.muted_until)
                    if now < mute_dt:
                        continue
                except ValueError:
                    pass

            score, matched_kw, matched_tk = self._score(ping, text, content_tickers)
            if score >= ping.min_relevance:
                item_id = content.get("article_id") or content.get("accession", "")
                m = PingMatch(
                    ping=ping,
                    relevance_score=round(score, 3),
                    matched_keywords=matched_kw,
                    matched_tickers=matched_tk,
                    source_item_id=item_id,
                    source_type=source_type,
                    fired_at=now.isoformat(),
                )
                self.store.record_fire(m)
                matches.append(m)

        return sorted(matches, key=lambda m: -m.relevance_score)

    def _score(self, ping: Ping, text: str, content_tickers: list[str]) -> tuple:
        """
        Compute relevance score 0–1 for a ping against content text.
        Pure keyword + ticker matching — no AI.
        """
        matched_kw: list[str] = []
        matched_tk: list[str] = []

        # Keyword hits
        kw_hits = 0
        for kw in ping.keywords:
            if kw in text:
                matched_kw.append(kw)
                kw_hits += 1

        kw_score = min(kw_hits / max(len(ping.keywords), 1), 1.0)

        # Ticker hits (bonus)
        tk_score = 0.0
        for tk in ping.tickers:
            if tk.upper() in content_tickers:
                matched_tk.append(tk)
                tk_score = 1.0  # any ticker match is a strong signal

        # Priority weight modulates threshold but not score itself
        raw_score = kw_score * 0.6 + tk_score * 0.4

        return raw_score, matched_kw, matched_tk

    def bulk_match(
        self,
        items: list[dict],
        source_type: str = "news",
    ) -> dict[str, list[PingMatch]]:
        """
        Match a batch of items against all pings.
        Returns {item_id: [PingMatch, ...]}
        """
        result: dict[str, list[PingMatch]] = {}
        for item in items:
            matches = self.match_content(item, source_type)
            if matches:
                item_id = item.get("article_id") or item.get("accession", "?")
                result[item_id] = matches
        return result


# ---------------------------------------------------------------------------
# CLI demo
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    pinger = TopicPinger(user_id="demo")

    if len(sys.argv) > 1 and sys.argv[1] == "add":
        topic = " ".join(sys.argv[2:]) or "Federal Reserve rate hike"
        p = pinger.ping(topic)
        print(f"Created ping: {p.ping_id}")
        print(f"  Keywords: {p.keywords}")
        print(f"  Tickers:  {p.tickers}")
        print(f"  Industry: {p.industry}")
    elif len(sys.argv) > 1 and sys.argv[1] == "list":
        for p in pinger.list_pings():
            muted = f" [muted until {p.muted_until[:16]}]" if p.muted_until else ""
            print(f"  [{p.priority}] {p.topic!r} → {p.keywords[:3]}{muted}")
    else:
        print("Demo: adding sample pings and matching test article")
        pinger.ping("war between Iran and USA", priority="HIGH")
        pinger.ping("NVDA", priority="CRITICAL", tickers=["NVDA"])
        pinger.ping("Federal Reserve rate decision", priority="MEDIUM")

        article = {
            "article_id": "demo001",
            "title": "Iran threatens to close Strait of Hormuz amid US sanctions",
            "summary": "Iran escalates tensions as new US oil sanctions take effect",
            "full_text": "Tehran — Iran threatened on Tuesday to block oil shipments through "
                         "the Strait of Hormuz in retaliation for US sanctions...",
            "tickers_mentioned": ["XOM", "CVX"],
        }
        matches = pinger.match_content(article, source_type="news")
        print(f"\nMatches for '{article['title'][:60]}':")
        for m in matches:
            print(f"  [{m.ping.priority}] '{m.ping.topic}' "
                  f"score={m.relevance_score:.2f} kw={m.matched_keywords}")
