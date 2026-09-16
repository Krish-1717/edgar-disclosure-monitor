"""
diff_sections.py — Compute paragraph-level diffs between consecutive filings.

Day 3: The core detection engine.

For each (company, form_type, item_key) triple, this module:
  1. Finds the two most recent filings that have the section segmented.
  2. Splits both section bodies into paragraphs.
  3. Aligns paragraphs using SequenceMatcher (difflib, Ratcliff/Obershelp).
  4. Classifies each aligned pair as: added / removed / revised / unchanged.
  5. Writes rows to the paragraph_diffs table.

Schema:
    paragraph_diffs(
        id, new_filing_id, prior_filing_id, item_key,
        change_type  CHECK(added/removed/revised/unchanged),
        prior_text, new_text, similarity, word_diff_json
    )

Similarity threshold:
  - similarity >= 0.95  → unchanged
  - 0.60 <= sim < 0.95  → revised
  - sim < 0.60 AND new has text → added (no counterpart in prior)
  - sim < 0.60 AND prior has text → removed

word_diff_json stores the word-level diff as a JSON list of
  [tag, text] pairs where tag ∈ {equal, insert, delete, replace}.

Run modes:
  python -m edgar.diff_sections                     # all pairs
  python -m edgar.diff_sections --ticker AAPL        # one company
  python -m edgar.diff_sections --dry_run            # print summary only
"""

import sqlite3
import json
import argparse
import difflib
import re
from pathlib import Path
from dataclasses import dataclass, field

# ── Constants ──────────────────────────────────────────────────────────────────

UNCHANGED_THRESHOLD = 0.95
REVISED_THRESHOLD   = 0.60

DB_PATH     = Path(__file__).parent.parent / "edgar_monitor.db"
SCHEMA_PATH = Path(__file__).parent.parent / "db" / "schema.sql"

# ── Paragraph splitting ───────────────────────────────────────────────────────

def _split_paragraphs(text: str) -> list[str]:
    """
    Split section body into paragraphs.
    A paragraph boundary is one or more blank lines.
    Short paragraphs (<15 words) are merged with the next paragraph.
    """
    raw = re.split(r"\n{2,}", text.strip())
    # Normalise each paragraph
    paras = [re.sub(r"\s+", " ", p.strip()) for p in raw if p.strip()]

    # Merge orphan short paragraphs (page headers, "PART I" type labels)
    merged: list[str] = []
    buffer = ""
    for p in paras:
        if buffer:
            buffer = buffer + " " + p
            if len(buffer.split()) >= 15:
                merged.append(buffer)
                buffer = ""
        elif len(p.split()) < 15:
            buffer = p
        else:
            merged.append(p)
    if buffer:
        merged.append(buffer)

    return merged if merged else paras


# ── Word-level diff ───────────────────────────────────────────────────────────

def _word_diff_json(prior: str, new: str) -> str:
    """
    Return a JSON list of [tag, text] pairs representing the word-level diff.
    Tags: equal, insert, delete, replace (mapped from difflib opcodes).
    """
    prior_words = prior.split()
    new_words   = new.split()
    sm = difflib.SequenceMatcher(None, prior_words, new_words, autojunk=False)
    result = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            result.append(["equal",   " ".join(prior_words[i1:i2])])
        elif tag == "insert":
            result.append(["insert",  " ".join(new_words[j1:j2])])
        elif tag == "delete":
            result.append(["delete",  " ".join(prior_words[i1:i2])])
        elif tag == "replace":
            result.append(["delete",  " ".join(prior_words[i1:i2])])
            result.append(["insert",  " ".join(new_words[j1:j2])])
    return json.dumps(result, ensure_ascii=False)


# ── Paragraph alignment ───────────────────────────────────────────────────────

@dataclass
class ParaDiff:
    change_type:    str   # added / removed / revised / unchanged
    prior_text:     str
    new_text:       str
    similarity:     float
    word_diff_json: str


def _classify(prior: str, new: str) -> ParaDiff:
    """Classify a (prior, new) paragraph pair."""
    ratio = difflib.SequenceMatcher(None, prior, new, autojunk=False).ratio()
    if ratio >= UNCHANGED_THRESHOLD:
        ct = "unchanged"
    elif ratio >= REVISED_THRESHOLD:
        ct = "revised"
    elif new and not prior:
        ct = "added"
        ratio = 0.0
    elif prior and not new:
        ct = "removed"
        ratio = 0.0
    else:
        ct = "revised"

    wdj = _word_diff_json(prior, new) if ct in ("revised", "unchanged") else "[]"
    return ParaDiff(change_type=ct, prior_text=prior, new_text=new,
                    similarity=round(ratio, 4), word_diff_json=wdj)


def align_paragraphs(prior_paras: list[str], new_paras: list[str]) -> list[ParaDiff]:
    """
    Align two paragraph lists using SequenceMatcher opcodes.
    Returns one ParaDiff per aligned pair/singleton.
    """
    sm = difflib.SequenceMatcher(None, prior_paras, new_paras, autojunk=False)
    diffs: list[ParaDiff] = []

    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            for p, n in zip(prior_paras[i1:i2], new_paras[j1:j2]):
                diffs.append(_classify(p, n))
        elif tag == "replace":
            # Pair up as many as we can; remainder are added/removed
            prior_chunk = prior_paras[i1:i2]
            new_chunk   = new_paras[j1:j2]
            for p, n in zip(prior_chunk, new_chunk):
                diffs.append(_classify(p, n))
            for p in prior_chunk[len(new_chunk):]:
                diffs.append(ParaDiff("removed", p, "", 0.0, "[]"))
            for n in new_chunk[len(prior_chunk):]:
                diffs.append(ParaDiff("added", "", n, 0.0, "[]"))
        elif tag == "insert":
            for n in new_paras[j1:j2]:
                diffs.append(ParaDiff("added", "", n, 0.0, "[]"))
        elif tag == "delete":
            for p in prior_paras[i1:i2]:
                diffs.append(ParaDiff("removed", p, "", 0.0, "[]"))

    return diffs


# ── DB helpers ────────────────────────────────────────────────────────────────

def _open_db() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA foreign_keys=ON")
    con.executescript(SCHEMA_PATH.read_text())
    return con


def _filing_pairs(con: sqlite3.Connection, ticker: str | None = None) -> list[tuple]:
    """
    For each (cik, form_type, item_key) triple, find the two most recent
    filings that have sections, and return (new_filing_id, prior_filing_id, item_key).
    Skip pairs already diffed.
    """
    ticker_filter = "AND f.ticker = :ticker" if ticker else ""
    sql = f"""
        WITH ranked AS (
            SELECT
                s.filing_id,
                s.item_key,
                f.cik,
                f.form_type,
                f.filing_date,
                ROW_NUMBER() OVER (
                    PARTITION BY f.cik, f.form_type, s.item_key
                    ORDER BY f.filing_date DESC
                ) AS rn
            FROM sections s
            JOIN filings f ON f.id = s.filing_id
            {ticker_filter}
        ),
        pairs AS (
            SELECT
                r1.filing_id AS new_id,
                r2.filing_id AS prior_id,
                r1.item_key
            FROM ranked r1
            JOIN ranked r2
              ON r1.cik = r2.cik
             AND r1.form_type = r2.form_type
             AND r1.item_key  = r2.item_key
             AND r1.rn = 1
             AND r2.rn = 2
        )
        SELECT p.new_id, p.prior_id, p.item_key
        FROM pairs p
        WHERE NOT EXISTS (
            SELECT 1 FROM paragraph_diffs pd
            WHERE pd.new_filing_id   = p.new_id
              AND pd.prior_filing_id = p.prior_id
              AND pd.item_key        = p.item_key
        )
    """
    params = {"ticker": ticker.upper()} if ticker else {}
    return con.execute(sql, params).fetchall()


def _get_section_text(con: sqlite3.Connection, filing_id: int, item_key: str) -> str:
    row = con.execute(
        "SELECT body_text FROM sections WHERE filing_id=? AND item_key=?",
        (filing_id, item_key),
    ).fetchone()
    return row["body_text"] if row else ""


def _insert_diffs(
    con: sqlite3.Connection,
    new_filing_id: int,
    prior_filing_id: int,
    item_key: str,
    diffs: list[ParaDiff],
) -> int:
    inserted = 0
    for d in diffs:
        con.execute(
            """
            INSERT INTO paragraph_diffs
              (new_filing_id, prior_filing_id, item_key,
               change_type, prior_text, new_text, similarity, word_diff_json)
            VALUES (?,?,?,?,?,?,?,?)
            """,
            (new_filing_id, prior_filing_id, item_key,
             d.change_type, d.prior_text, d.new_text,
             d.similarity, d.word_diff_json),
        )
        inserted += 1
    con.commit()
    return inserted


# ── Main runner ───────────────────────────────────────────────────────────────

def diff_all(ticker: str | None = None, dry_run: bool = False) -> None:
    con = _open_db()
    pairs = _filing_pairs(con, ticker)
    total = len(pairs)
    print(f"Filing pairs to diff: {total}")
    if not total:
        print("Nothing to do.")
        return

    total_diffs = 0
    for i, row in enumerate(pairs, 1):
        new_id   = row["new_id"]
        prior_id = row["prior_id"]
        key      = row["item_key"]

        prior_text = _get_section_text(con, prior_id, key)
        new_text   = _get_section_text(con, new_id, key)

        prior_paras = _split_paragraphs(prior_text) if prior_text else []
        new_paras   = _split_paragraphs(new_text)   if new_text   else []

        diffs = align_paragraphs(prior_paras, new_paras)
        changed = [d for d in diffs if d.change_type != "unchanged"]

        counts = {}
        for d in diffs:
            counts[d.change_type] = counts.get(d.change_type, 0) + 1

        print(f"[{i}/{total}] filing {prior_id}→{new_id}  {key:6s}  "
              f"paras={len(diffs)}  changed={len(changed)}  {counts}")

        if dry_run:
            continue

        n = _insert_diffs(con, new_id, prior_id, key, diffs)
        total_diffs += n

    con.close()
    print(f"\nDone. Total diff rows inserted: {total_diffs}")


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    p = argparse.ArgumentParser(
        description="Compute paragraph-level diffs between consecutive filings."
    )
    p.add_argument("--ticker",  help="Restrict to one company")
    p.add_argument("--dry_run", action="store_true", help="Print only, no writes")
    args = p.parse_args()
    diff_all(ticker=args.ticker, dry_run=args.dry_run)
