"""
risk_scorer.py — Red-flag risk signal scorer for SEC filings.

Scans filing text for regulatory patterns: going concern, material weakness,
litigation, restatement, related party, cybersecurity, and more.
Returns scored, ranked RiskSignal objects.

Usage:
    scorer = RiskScorer()
    result = scorer.score(filing_text, ticker="NVDA", form_type="10-K")
    for sig in result.signals[:5]:
        print(sig)
"""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Risk signal definitions
# ---------------------------------------------------------------------------

@dataclass
class SignalPattern:
    category: str
    name: str
    patterns: list          # list of regex strings
    base_score: float       # 0-1 base severity
    description: str


SIGNAL_PATTERNS: list[SignalPattern] = [
    SignalPattern(
        category="going_concern",
        name="Going Concern",
        patterns=[
            r"going\s+concern",
            r"substantial\s+doubt.{0,50}ability\s+to\s+continue",
            r"ability\s+to\s+continue\s+as\s+a\s+going\s+concern",
        ],
        base_score=0.95,
        description="Auditor doubts company can survive next 12 months",
    ),
    SignalPattern(
        category="material_weakness",
        name="Material Weakness",
        patterns=[
            r"material\s+weakness",
            r"significant\s+deficiency.{0,60}internal\s+control",
            r"restat(?:e|ed|ement).{0,30}financial\s+statement",
        ],
        base_score=0.90,
        description="Internal control deficiency requiring restatement or correction",
    ),
    SignalPattern(
        category="fraud",
        name="Fraud / Misconduct",
        patterns=[
            r"\bfraud\b",
            r"accounting\s+irregularit",
            r"misappropriation",
            r"embezzlement",
            r"falsif(?:ied|ication)",
            r"willful\s+misrepresent",
        ],
        base_score=0.95,
        description="Fraud, embezzlement, or deliberate misrepresentation disclosed",
    ),
    SignalPattern(
        category="sec_investigation",
        name="SEC / Regulatory Investigation",
        patterns=[
            r"sec\s+(?:investigation|inquiry|subpoena|enforcement)",
            r"department\s+of\s+justice.{0,30}investigat",
            r"grand\s+jury\s+subpoena",
            r"wells\s+notice",
            r"formal\s+order\s+of\s+investigation",
        ],
        base_score=0.92,
        description="SEC, DOJ, or other regulator opened formal investigation",
    ),
    SignalPattern(
        category="litigation",
        name="Material Litigation",
        patterns=[
            r"class\s+action",
            r"derivative\s+(?:lawsuit|suit|action|litigation)",
            r"material\s+(?:adverse|litigation)",
            r"criminal\s+(?:indictment|charge|prosecution)",
            r"whistleblower\s+(?:claim|complaint|lawsuit)",
        ],
        base_score=0.80,
        description="Significant litigation or class action exposure",
    ),
    SignalPattern(
        category="restatement",
        name="Financial Restatement",
        patterns=[
            r"restat(?:e|ed|ement|ing)\s+(?:its\s+)?(?:previously\s+)?(?:issued\s+)?financial",
            r"non-reliance.{0,80}financial\s+statement",
            r"8-k.{0,30}item\s+4\.02",
        ],
        base_score=0.92,
        description="Prior financial statements restated or deemed non-reliable",
    ),
    SignalPattern(
        category="related_party",
        name="Related Party Transactions",
        patterns=[
            r"related[\s-]party\s+transaction",
            r"transactions\s+with\s+related\s+parties",
            r"conflict\s+of\s+interest.{0,80}officer",
            r"self[\s-]dealing",
        ],
        base_score=0.65,
        description="Undisclosed or unusual related-party transactions",
    ),
    SignalPattern(
        category="cybersecurity",
        name="Cybersecurity Incident",
        patterns=[
            r"data\s+breach",
            r"cyber(?:security)?\s+(?:attack|incident|intrusion|breach)",
            r"ransomware",
            r"unauthorized\s+access.{0,80}(?:data|system|network)",
        ],
        base_score=0.78,
        description="Material cybersecurity breach or data loss incident",
    ),
    SignalPattern(
        category="debt_default",
        name="Debt Default / Covenant Breach",
        patterns=[
            r"event\s+of\s+default",
            r"covenant\s+(?:breach|violation|default|waiver)",
            r"acceleration\s+of\s+(?:debt|indebtedness|maturity)",
            r"cross[\s-]default",
        ],
        base_score=0.87,
        description="Debt default or loan covenant breach disclosed",
    ),
    SignalPattern(
        category="impairment",
        name="Goodwill / Asset Impairment",
        patterns=[
            r"goodwill\s+impairment",
            r"intangible\s+asset\s+impairment",
            r"impairment\s+charge.{0,30}\$[\d\.]+\s*(?:million|billion)",
            r"write[\s-]down.{0,30}(?:goodwill|asset|inventory)",
        ],
        base_score=0.72,
        description="Material write-down of goodwill or long-lived assets",
    ),
    SignalPattern(
        category="bankruptcy",
        name="Bankruptcy / Restructuring",
        patterns=[
            r"chapter\s+11",
            r"chapter\s+7",
            r"petition\s+for\s+bankruptcy",
            r"voluntary\s+petition.{0,30}united\s+states\s+bankruptcy",
            r"plan\s+of\s+reorganization",
        ],
        base_score=0.98,
        description="Filed for or contemplating bankruptcy protection",
    ),
    SignalPattern(
        category="regulatory_action",
        name="Regulatory Action / Sanction",
        patterns=[
            r"consent\s+order",
            r"cease[\s-]and[\s-]desist",
            r"regulatory\s+sanction",
            r"fda\s+(?:warning\s+letter|import\s+alert|consent\s+decree)",
            r"ofac\s+(?:sanction|penalty|fine)",
        ],
        base_score=0.83,
        description="Formal regulatory action, sanction, or consent decree",
    ),
    SignalPattern(
        category="executive_departure",
        name="Key Executive Departure",
        patterns=[
            r"ceo\s+(?:resign|terminat|depart|step(?:ping)?\s+down)",
            r"chief\s+executive.{0,30}(?:resign|terminat|depart)",
            r"cfo\s+(?:resign|terminat|depart)",
            r"sudden\s+(?:departure|resignation).{0,40}officer",
        ],
        base_score=0.68,
        description="Sudden departure of key executive",
    ),
    SignalPattern(
        category="going_private",
        name="Going Private / Delisting Risk",
        patterns=[
            r"going[\s-]private\s+transaction",
            r"delisting\s+(?:notice|warning|threat)",
            r"nasdaq\s+(?:deficiency|delisting)",
            r"nyse\s+(?:deficiency|delisting)",
            r"minimum\s+bid\s+price\s+requirement",
        ],
        base_score=0.75,
        description="Delisting risk or going-private transaction",
    ),
]


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class RiskSignal:
    category: str
    name: str
    description: str
    score: float
    match_count: int
    excerpts: list = field(default_factory=list)   # up to 3 matched excerpts
    section_hits: list = field(default_factory=list)

    def __str__(self):
        return (f"[{self.score:.2f}] {self.name} ({self.match_count} hits) — "
                f"{self.description}")


@dataclass
class FilingRiskScore:
    ticker: str
    form_type: str
    filing_date: str
    composite_score: float     # 0-1 weighted aggregate
    signals: list              # list[RiskSignal] sorted by score desc
    categories_hit: list
    total_matches: int
    generated_at: str

    def __str__(self):
        return (
            f"Risk Report: {self.ticker} {self.form_type} ({self.filing_date})\n"
            f"Composite: {self.composite_score:.2f} | "
            f"Signals: {len(self.signals)} | Matches: {self.total_matches}\n"
            + "\n".join(f"  {s}" for s in self.signals[:5])
        )


# ---------------------------------------------------------------------------
# Risk Scorer
# ---------------------------------------------------------------------------

class RiskScorer:
    """
    Scans SEC filing text for red-flag risk signals.

    Scoring formula:
      - Each matched signal contributes: base_score * log(1 + match_count)
      - Composite = weighted average of top signals, capped at 1.0
    """

    def __init__(
        self,
        patterns: list = None,
        max_excerpts: int = 3,
        excerpt_window: int = 200,
        db_path: Optional[Path] = None,
    ):
        self.patterns = patterns or SIGNAL_PATTERNS
        self.max_excerpts = max_excerpts
        self.excerpt_window = excerpt_window
        self.db_path = db_path
        if db_path:
            db_path.parent.mkdir(parents=True, exist_ok=True)
            self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS risk_scores (
                    id             INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticker         TEXT,
                    form_type      TEXT,
                    filing_date    TEXT,
                    composite_score REAL,
                    categories_hit TEXT,
                    total_matches  INTEGER,
                    scored_at      TEXT
                )
            """)

    def _match_pattern(self, pattern: SignalPattern, text: str) -> tuple:
        """Returns (match_count, excerpts)."""
        text_lower = text.lower()
        excerpts = []
        positions = []
        for regex in pattern.patterns:
            for m in re.finditer(regex, text_lower):
                positions.append(m.start())

        match_count = len(positions)
        for pos in positions[:self.max_excerpts]:
            start = max(0, pos - 50)
            end   = min(len(text), pos + self.excerpt_window)
            excerpts.append(text[start:end].replace("\n", " ").strip())

        return match_count, excerpts

    def score(
        self,
        filing_text: str,
        ticker: str = "",
        form_type: str = "10-K",
        filing_date: str = "",
    ) -> FilingRiskScore:
        """
        Score a filing text. Returns FilingRiskScore with ranked signals.
        """
        if not filing_date:
            filing_date = datetime.utcnow().strftime("%Y-%m-%d")

        signals = []
        for pattern in self.patterns:
            match_count, excerpts = self._match_pattern(pattern, filing_text)
            if match_count == 0:
                continue
            import math
            score = min(pattern.base_score * math.log1p(match_count), 1.0)
            signals.append(RiskSignal(
                category=pattern.category,
                name=pattern.name,
                description=pattern.description,
                score=round(score, 4),
                match_count=match_count,
                excerpts=excerpts,
            ))

        signals.sort(key=lambda s: -s.score)
        categories_hit = [s.category for s in signals]
        total_matches = sum(s.match_count for s in signals)

        # Composite: mean of top 3 signal scores, or 0
        top_scores = [s.score for s in signals[:3]]
        composite = round(sum(top_scores) / max(len(top_scores), 1), 4) if top_scores else 0.0

        result = FilingRiskScore(
            ticker=ticker,
            form_type=form_type,
            filing_date=filing_date,
            composite_score=composite,
            signals=signals,
            categories_hit=categories_hit,
            total_matches=total_matches,
            generated_at=datetime.utcnow().isoformat(),
        )

        if self.db_path:
            self._persist(result)

        return result

    def _persist(self, result: FilingRiskScore) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT INTO risk_scores
                   (ticker, form_type, filing_date, composite_score,
                    categories_hit, total_matches, scored_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (result.ticker, result.form_type, result.filing_date,
                 result.composite_score, json.dumps(result.categories_hit),
                 result.total_matches, result.generated_at),
            )

    def score_batch(self, filings: list) -> list:
        """
        Score multiple filings.
        filings: list of dicts with keys: text, ticker, form_type, filing_date
        """
        return [
            self.score(
                f.get("text", ""),
                ticker=f.get("ticker", ""),
                form_type=f.get("form_type", "10-K"),
                filing_date=f.get("filing_date", ""),
            )
            for f in filings
        ]

    def export_json(self, result: FilingRiskScore, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump({
                "ticker": result.ticker,
                "form_type": result.form_type,
                "filing_date": result.filing_date,
                "composite_score": result.composite_score,
                "categories_hit": result.categories_hit,
                "total_matches": result.total_matches,
                "generated_at": result.generated_at,
                "signals": [asdict(s) for s in result.signals],
            }, f, indent=2)


if __name__ == "__main__":
    scorer = RiskScorer()
    sample_text = """
    ITEM 1A. RISK FACTORS
    The Company has incurred significant losses and there is substantial doubt
    about our ability to continue as a going concern. 

    Our independent auditors identified a material weakness in our internal
    controls over financial reporting related to revenue recognition.

    The Company has received a formal order of investigation from the SEC
    regarding certain related-party transactions with our CEO.

    During fiscal 2026, we experienced a cybersecurity incident involving
    unauthorized access to customer data, constituting a data breach.

    We are subject to class action litigation filed in the Southern District
    of New York alleging securities fraud.
    """
    result = scorer.score(sample_text, ticker="DEMO", form_type="10-K",
                          filing_date="2026-10-01")
    print(result)
