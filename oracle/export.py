"""Static JSON feeds for the GitHub Pages site.

Pages is a static host, so visitors can't reach a local FastAPI server. ``python -m
oracle export --out DIR`` writes:

    DIR/index.json               manifest: generated_at + one row per company
    DIR/companies/{TICKER}.json  the same payload as GET /companies/{ticker}/feed

Feeds are small (section excerpts, not full text), ASCII-only (``\\uXXXX`` escapes,
per the repo's encoding rule) and shaped like ``FILING_DATA`` in assets/js/app.js
(``id``, ``form``, ``date``, ``group``) plus real SEC links and section changes vs
the previous filing of the same form.
"""
from __future__ import annotations

import datetime as dt
import json
import pathlib
import re

from . import __version__
from .storage import Store, utcnow

FEED_SCHEMA = 1
EXCERPT_CHARS = 600
SNIPPET_CHARS = 320
MAX_SNIPPETS = 3

GROUPS = {
    "10-K": "annual", "10-Q": "quarterly", "8-K": "event", "DEF 14A": "proxy",
    "4": "insider", "S-1": "registration", "S-4": "registration",
}
_DIGITS_RE = re.compile(r"\d[\d,.]*")
_WS_RE = re.compile(r"\s+")


def _display_date(iso: str) -> str:
    try:
        d = dt.date.fromisoformat(iso)
    except (TypeError, ValueError):
        return iso or ""
    return f"{d.strftime('%b')} {d.day}, {d.year}"


def _label(form: str, iso: str) -> str:
    try:
        d = dt.date.fromisoformat(iso)
        return f"{form} {d.strftime('%b')} '{d.strftime('%y')}"
    except (TypeError, ValueError):
        return form


def _paragraphs(text: str, min_words: int = 15) -> list[str]:
    out = []
    for p in re.split(r"\n\s*\n|\n", text):
        p = _WS_RE.sub(" ", p).strip()
        if len(p.split()) >= min_words:
            out.append(p)
    return out


UNCHANGED_SIM = 0.8   # word-set Jaccard >= this: same paragraph (minor edits, new numbers)
MODIFIED_SIM = 0.5    # between the two: reworded paragraph (reported as before/after)


def _tokens(p: str) -> frozenset[str]:
    # Numbers change every period; compare paragraphs on their wording.
    return frozenset(re.findall(r"[a-z#]+", _DIGITS_RE.sub("#", p.lower())))


def _jaccard(a: frozenset, b: frozenset) -> float:
    return len(a & b) / len(a | b) if a or b else 1.0


def _best(tok: frozenset, pool: list[frozenset]) -> tuple[float, int]:
    best, idx = 0.0, -1
    for j, other in enumerate(pool):
        sim = _jaccard(tok, other)
        if sim > best:
            best, idx = sim, j
            if sim == 1.0:
                break
    return best, idx


def _clip(text: str, n: int) -> str:
    return text if len(text) <= n else text[: n - 3].rsplit(" ", 1)[0] + "..."


def _diff_window(before: str, after: str, lead_words: int = 6) -> tuple[str, str]:
    """Clip a before/after pair so both snippets start just before the first wording change."""
    b, a = before.split(), after.split()
    i = 0
    while i < min(len(b), len(a)) and b[i] == a[i]:
        i += 1
    start = i - lead_words if i > 2 * lead_words else 0   # early changes: keep the opening
    pre = "..." if start else ""
    return (_clip(pre + " ".join(b[start:]), SNIPPET_CHARS), _clip(pre + " ".join(a[start:]), SNIPPET_CHARS))


def section_change(prev_text: str | None, cur_text: str) -> dict | None:
    """Paragraph-level change summary vs the previous filing. ``None`` if nothing to compare.

    Each current paragraph is matched to its most similar previous paragraph by word
    overlap: unchanged (>= 0.8), modified (>= 0.5, reported as before/after), or added.
    Previous paragraphs with no match >= 0.5 are removed. ``change_ratio`` is the share
    of paragraphs that are not unchanged: (added + modified + removed) / (current + removed).
    """
    if prev_text is None:
        return None
    prev, cur = _paragraphs(prev_text), _paragraphs(cur_text)
    prev_tok, cur_tok = [_tokens(p) for p in prev], [_tokens(p) for p in cur]
    added, modified = [], []
    for p, tok in zip(cur, cur_tok):
        sim, j = _best(tok, prev_tok)
        if sim >= UNCHANGED_SIM:
            continue
        if sim >= MODIFIED_SIM:
            modified.append((sim, prev[j], p))
        else:
            added.append(p)
    removed = [p for p, tok in zip(prev, prev_tok) if _best(tok, cur_tok)[0] < MODIFIED_SIM]
    denom = len(cur) + len(removed)
    words_prev, words_cur = len(prev_text.split()), len(cur_text.split())
    modified.sort(key=lambda m: m[0])   # most reworded first
    return {
        "words_prev": words_prev,
        "words": words_cur,
        "word_delta_pct": round(100.0 * (words_cur - words_prev) / words_prev, 1) if words_prev else None,
        "paragraphs": len(cur),
        "paragraphs_added": len(added),
        "paragraphs_modified": len(modified),
        "paragraphs_removed": len(removed),
        "change_ratio": round((len(added) + len(modified) + len(removed)) / denom, 3) if denom else 0.0,
        "added_samples": [_clip(p, SNIPPET_CHARS) for p in sorted(added, key=len, reverse=True)[:MAX_SNIPPETS]],
        "modified_samples": [dict(zip(("before", "after"), _diff_window(b, a)), similarity=round(sim, 2))
                             for sim, b, a in modified[:MAX_SNIPPETS]],
        "removed_samples": [_clip(p, SNIPPET_CHARS) for p in sorted(removed, key=len, reverse=True)[:MAX_SNIPPETS]],
    }


def _previous_same_form(rows: list[dict], i: int) -> dict | None:
    """rows are newest first; the previous original filing of the same base form."""
    cur = rows[i]
    for r in rows[i + 1:]:
        if r["base_form"] == cur["base_form"] and not r["is_amendment"] and r["status"] == "fetched":
            return r
    return None


def build_company_feed(store: Store, ticker: str, limit: int = 100) -> dict | None:
    company = store.get_company(ticker)
    if not company:
        return None
    rows = store.list_filings(company["cik"], limit=limit)
    filings = []
    for i, r in enumerate(rows):
        secs = store.sections_for(r["accession"], include_text=True)
        prev = _previous_same_form(rows, i) if secs else None
        prev_secs = {s["key"]: s["text"] for s in store.sections_for(prev["accession"], include_text=True)} if prev else {}
        sections = []
        for s in secs:
            sections.append({
                "key": s["key"],
                "item": s["item"],
                "title": s["title"],
                "chars": s["char_count"],
                "excerpt": _clip(_WS_RE.sub(" ", s["text"]).strip(), EXCERPT_CHARS),
                "change": section_change(prev_secs.get(s["key"]), s["text"]) if prev else None,
            })
        filings.append({
            "id": _label(r["form"], r["filing_date"]),
            "accession": r["accession"],
            "form": r["form"],
            "base_form": r["base_form"],
            "group": GROUPS.get(r["base_form"], "other"),
            "date": _display_date(r["filing_date"]),
            "filing_date": r["filing_date"],
            "report_date": r["report_date"],
            "is_amendment": bool(r["is_amendment"]),
            "version": r["version"],
            "amends_accession": r["amends_accession"],
            "items": r["items"].split(",") if r["items"] else [],
            "current": False,
            "status": r["status"],
            "sec_url": r["primary_doc_url"],
            "sha256": r["sha256"],
            "index_url": r["index_url"].replace("index.json", f"{r['accession']}-index.htm") if r["index_url"] else None,
            "compared_to": prev["accession"] if prev else None,
            "sections": sections,
        })
    for f in filings:   # most recent annual/quarterly report is the "current" one, as in the demo
        if f["group"] in ("annual", "quarterly") and f["status"] == "fetched":
            f["current"] = True
            break
    return {
        "schema": FEED_SCHEMA,
        "generated_at": utcnow(),
        "source": "SEC EDGAR via ORACLE " + __version__,
        "company": {
            "ticker": company["ticker"],
            "name": company["name"],
            "cik": f"{company['cik']:010d}",
            "last_crawled_at": company["last_crawled_at"],
        },
        "filings": filings,
    }


EXCHANGE_ORDER = {"NYSE": 0, "Nasdaq": 1, "CBOE": 2, "TXSE": 3, "OTC": 4}


def build_universe(rows: list[list]) -> dict:
    """All SEC-registered companies with a ticker (company_tickers_exchange.json).

    Compact for the static site: ``[ticker, name, cik, exchange]`` rows, listed
    exchanges first, then OTC / unlisted, alphabetical within each.
    """
    seen, out = set(), []
    for cik, name, ticker, exchange in rows:
        if not ticker or ticker in seen:
            continue
        seen.add(ticker)
        out.append([ticker, name, int(cik), exchange or ""])
    out.sort(key=lambda r: (EXCHANGE_ORDER.get(r[3], 9), r[0]))
    return {"schema": FEED_SCHEMA, "generated_at": utcnow(), "source": "SEC company_tickers_exchange.json",
            "fields": ["ticker", "name", "cik", "exchange"], "count": len(out), "companies": out}


def write_universe(client, out_path: str | pathlib.Path) -> dict:
    from .discovery import TICKERS_EXCHANGE_URL

    data = client.get_json(TICKERS_EXCHANGE_URL)
    universe = build_universe(data["data"])
    path = pathlib.Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(universe, ensure_ascii=True, separators=(",", ":")), encoding="ascii")
    return universe


def write_export(store: Store, out_dir: str | pathlib.Path, tickers: list[str] | None = None) -> dict:
    out = pathlib.Path(out_dir)
    (out / "companies").mkdir(parents=True, exist_ok=True)
    tickers = tickers or [c["ticker"] for c in store.list_companies()]
    manifest = {"schema": FEED_SCHEMA, "generated_at": utcnow(), "companies": []}
    for t in tickers:
        feed = build_company_feed(store, t)
        if not feed:
            continue
        path = out / "companies" / f"{feed['company']['ticker']}.json"
        path.write_text(json.dumps(feed, ensure_ascii=True, separators=(",", ":")), encoding="ascii")
        latest = feed["filings"][0] if feed["filings"] else None
        manifest["companies"].append({
            **feed["company"],
            "filings": len(feed["filings"]),
            "latest": {k: latest[k] for k in ("form", "filing_date", "accession")} if latest else None,
            "feed": f"companies/{path.name}",
        })
    (out / "index.json").write_text(json.dumps(manifest, ensure_ascii=True, indent=1), encoding="ascii")
    return manifest
