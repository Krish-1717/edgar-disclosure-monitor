"""
llm_classifier.py — LLM-Assisted Change Classification

Uses OpenAI GPT-4o-mini to:
  1. Classify what TYPE of change occurred (risk, strategy, legal, financial, etc.)
  2. Generate a plain-English one-sentence summary of the change
  3. Assign a severity label (MATERIAL / NOTABLE / ROUTINE)
  4. Extract a key quote (≤50 words) from the new text

Populates the llm_topic, llm_summary, llm_severity, llm_quote columns in the
`changes` table, which are currently written but never populated by the pipeline.

Usage:
    from llm_classifier import classify_changes, classify_alert_summary
    classify_changes(conn, new_filing_id=42)   # populates DB in place
"""
from __future__ import annotations
import json
import logging
import os
import time
import sqlite3
from typing import Optional

log = logging.getLogger(__name__)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
MODEL = "gpt-4o-mini"
MAX_TEXT_CHARS = 1200   # truncate long paragraphs before sending
RATE_LIMIT_SEC = 0.5    # courtesy pause between API calls

CHANGE_TYPES = [
    "risk_factor",        # new or escalated risk
    "legal",              # litigation, regulatory, government
    "financial",          # revenue, margins, capex, guidance
    "strategy",           # M&A, new products, geographic expansion
    "management",         # leadership, governance, compensation
    "operational",        # supply chain, manufacturing, headcount
    "esg",                # environmental, social, governance
    "accounting",         # policy changes, restatements
    "boilerplate",        # routine language update, no substance
]

SEVERITY_LEVELS = ["MATERIAL", "NOTABLE", "ROUTINE"]

_SYSTEM_PROMPT = """\
You are a financial analyst specializing in SEC filing analysis.
You will be given a paragraph from a company's 10-K or 10-Q filing (the NEW version)
and the prior version of the same paragraph (OLD version).
Respond ONLY with a JSON object matching this schema exactly:
{
  "topic":    "<one of: risk_factor | legal | financial | strategy | management | operational | esg | accounting | boilerplate>",
  "summary":  "<one sentence (≤25 words) describing what changed and why it matters>",
  "severity": "<MATERIAL | NOTABLE | ROUTINE>",
  "quote":    "<most important phrase or sentence from the NEW text, ≤40 words>"
}
Rules:
- MATERIAL: substantive change investors should know about
- NOTABLE: meaningful but not urgent
- ROUTINE: minor wording or formatting, no substance change
- If old text is empty, the paragraph is newly added.
- If new text is empty, the paragraph was removed.
- Prefer concise, analyst-grade language.
"""


def _openai_classify(new_text: str, old_text: str, ticker: str) -> dict:
    """Call GPT-4o-mini to classify one changed paragraph."""
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY not set — set it in .env to enable LLM classification")

    try:
        from openai import OpenAI
    except ImportError:
        raise RuntimeError("openai package not installed. Run: pip install openai")

    client = OpenAI(api_key=OPENAI_API_KEY)

    user_msg = (
        f"Company: {ticker}\n\n"
        f"NEW TEXT:\n{new_text[:MAX_TEXT_CHARS]}\n\n"
        f"OLD TEXT:\n{old_text[:MAX_TEXT_CHARS] if old_text else '(paragraph did not exist in prior filing)'}"
    )

    resp = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user",   "content": user_msg},
        ],
        temperature=0.2,
        max_tokens=200,
        response_format={"type": "json_object"},
    )

    raw = resp.choices[0].message.content or "{}"
    result = json.loads(raw)

    # Validate and sanitise
    topic    = result.get("topic", "boilerplate")
    if topic not in CHANGE_TYPES:
        topic = "boilerplate"
    severity = result.get("severity", "ROUTINE")
    if severity not in SEVERITY_LEVELS:
        severity = "ROUTINE"

    return {
        "topic":    topic,
        "summary":  str(result.get("summary", ""))[:500],
        "severity": severity,
        "quote":    str(result.get("quote", ""))[:400],
    }


def classify_changes(
    conn: sqlite3.Connection,
    new_filing_id: int,
    ticker: str = "",
    only_significant: bool = True,
    limit: int = 30,
) -> int:
    """
    Classify all unclassified 'revised' and 'added' changes for a filing.
    Writes results to the changes table (llm_topic, llm_summary, llm_severity, llm_quote).

    Parameters
    ----------
    conn              : open SQLite connection
    new_filing_id     : filing to classify
    ticker            : used in prompt for context
    only_significant  : if True, skip 'unchanged' and similarity > 0.95
    limit             : max changes to classify (cost control)

    Returns
    -------
    Number of changes classified
    """
    if not OPENAI_API_KEY:
        log.warning("OPENAI_API_KEY not set — skipping LLM classification")
        return 0

    # Resolve ticker if not provided
    if not ticker:
        row = conn.execute(
            "SELECT ticker FROM filings WHERE id=?", (new_filing_id,)
        ).fetchone()
        ticker = row["ticker"] if row else "UNKNOWN"

    query = """
        SELECT id, new_text, old_text, change_type, similarity
        FROM changes
        WHERE new_filing_id = ?
          AND llm_topic IS NULL
          AND change_type != 'unchanged'
        ORDER BY
            CASE change_type WHEN 'added' THEN 0 WHEN 'revised' THEN 1 ELSE 2 END,
            COALESCE(length(new_text), 0) DESC
        LIMIT ?
    """
    if only_significant:
        query = query.replace(
            "AND change_type != 'unchanged'",
            "AND change_type != 'unchanged' AND (similarity < 0.90 OR change_type = 'added')"
        )

    rows = conn.execute(query, (new_filing_id, limit)).fetchall()
    classified = 0

    for row in rows:
        try:
            result = _openai_classify(
                new_text=row["new_text"] or "",
                old_text=row["old_text"] or "",
                ticker=ticker,
            )
            conn.execute("""
                UPDATE changes
                SET llm_topic    = ?,
                    llm_summary  = ?,
                    llm_severity = ?,
                    llm_quote    = ?
                WHERE id = ?
            """, (
                result["topic"],
                result["summary"],
                result["severity"],
                result["quote"],
                row["id"],
            ))
            conn.commit()
            classified += 1
            log.debug("Classified change %d: %s / %s", row["id"], result["topic"], result["severity"])
        except Exception as e:
            log.warning("LLM classification failed for change %d: %s", row["id"], e)

        time.sleep(RATE_LIMIT_SEC)

    log.info("LLM-classified %d changes for filing %d (%s)", classified, new_filing_id, ticker)
    return classified


def classify_alert_summary(
    conn: sqlite3.Connection,
    alert_id: int,
) -> Optional[str]:
    """
    Generate a single executive summary for an entire alert using
    the top 5 classified changes. Returns the summary string or None.
    """
    if not OPENAI_API_KEY:
        return None

    try:
        from openai import OpenAI
    except ImportError:
        return None

    # Fetch alert + top changes
    alert = conn.execute("SELECT * FROM alerts WHERE id=?", (alert_id,)).fetchone()
    if not alert:
        return None

    changes = conn.execute("""
        SELECT item, change_type, llm_topic, llm_summary, llm_severity, new_text
        FROM changes
        WHERE new_filing_id = ?
          AND change_type != 'unchanged'
          AND llm_severity IN ('MATERIAL', 'NOTABLE')
        ORDER BY
            CASE llm_severity WHEN 'MATERIAL' THEN 0 ELSE 1 END,
            length(new_text) DESC
        LIMIT 5
    """, (alert["new_filing_id"],)).fetchall()

    if not changes:
        return None

    bullets = "\n".join(
        f"- Item {r['item']} [{r.get('llm_topic','?')}]: {r.get('llm_summary','')}"
        for r in changes
    )

    client = OpenAI(api_key=OPENAI_API_KEY)
    prompt = (
        f"Ticker: {alert['ticker']}\nFiled: {alert['filed']}\n"
        f"Materiality Score: {alert['materiality_score']:.1f}/100\n"
        f"Burial Score: {alert['burial_score']:.1f}/100\n\n"
        f"Top changes:\n{bullets}\n\n"
        "Write a 2–3 sentence executive summary of this filing's most important changes. "
        "Focus on investor-relevant insights. Be specific."
    )

    try:
        resp = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=150,
        )
        summary = resp.choices[0].message.content or ""
        # Store in alert
        conn.execute(
            "UPDATE alerts SET summary_items = json_set(summary_items, '$.exec_summary', ?) WHERE id=?",
            (summary, alert_id)
        )
        conn.commit()
        return summary
    except Exception as e:
        log.warning("Executive summary generation failed for alert %d: %s", alert_id, e)
        return None


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    from database import get_connection, init_db
    conn = get_connection()
    init_db(conn)
    # Test: classify 5 changes from the most recent filing
    row = conn.execute("SELECT id, ticker FROM filings ORDER BY id DESC LIMIT 1").fetchone()
    if row:
        n = classify_changes(conn, row["id"], ticker=row["ticker"], limit=5)
        print(f"Classified {n} changes for {row['ticker']} filing {row['id']}")
    else:
        print("No filings in DB yet. Run the pipeline first.")
