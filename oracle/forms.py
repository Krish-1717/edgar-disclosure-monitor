"""Form-specific extraction: Form 4 transaction tables and 8-K Exhibit 99.1 press releases."""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET

from . import extract

# Form 4 transaction codes (SEC Form 4 General Instructions, section 8)
TX_CODES = {
    "P": "Open-market purchase", "S": "Open-market sale", "A": "Grant or award", "M": "Option exercise",
    "F": "Shares withheld for tax", "G": "Gift", "D": "Disposition to issuer", "C": "Conversion",
    "X": "Option exercise (in the money)", "J": "Other", "W": "Will or inheritance", "I": "Discretionary",
    "V": "Voluntarily reported", "K": "Equity swap",
}


def _t(el, path: str) -> str:
    """Text at path, looking through the <value> wrapper Form 4 uses for most fields."""
    if el is None:
        return ""
    node = el.find(path)
    if node is None:
        return ""
    v = node.find("value")
    txt = (v.text if v is not None else node.text) or ""
    return txt.strip()


def _num(s: str) -> float | None:
    try:
        return float(s.replace(",", ""))
    except (TypeError, ValueError):
        return None


def parse_form4(xml_bytes: bytes) -> dict | None:
    """Reporting owners plus non-derivative and derivative transactions."""
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return None
    if root.tag != "ownershipDocument":
        inner = root.find(".//ownershipDocument")
        if inner is not None:
            root = inner
    owners = []
    for ro in root.findall("reportingOwner"):
        rel = ro.find("reportingOwnerRelationship")
        roles = []
        if rel is not None:
            if _t(rel, "isDirector") in ("1", "true"):
                roles.append("Director")
            if _t(rel, "isOfficer") in ("1", "true"):
                roles.append(_t(rel, "officerTitle") or "Officer")
            if _t(rel, "isTenPercentOwner") in ("1", "true"):
                roles.append("10% owner")
            if _t(rel, "isOther") in ("1", "true"):
                roles.append(_t(rel, "otherText") or "Other")
        owners.append({"name": _t(ro, "reportingOwnerId/rptOwnerName"), "roles": roles})

    plan = _t(root, "aff10b5One") in ("1", "true")
    txs = []
    for kind, path in (("common", "nonDerivativeTable/nonDerivativeTransaction"),
                       ("derivative", "derivativeTable/derivativeTransaction")):
        for tx in root.findall(path):
            code = _t(tx, "transactionCoding/transactionCode")
            shares = _num(_t(tx, "transactionAmounts/transactionShares"))
            price = _num(_t(tx, "transactionAmounts/transactionPricePerShare"))
            txs.append({
                "kind": kind,
                "security": _t(tx, "securityTitle"),
                "date": _t(tx, "transactionDate"),
                "code": code,
                "what": TX_CODES.get(code, code),
                "ad": _t(tx, "transactionAmounts/transactionAcquiredDisposedCode"),   # A acquired, D disposed
                "shares": shares,
                "price": price,
                "value": round(shares * price, 2) if shares is not None and price else None,
                "after": _num(_t(tx, "postTransactionAmounts/sharesOwnedFollowingTransaction")),
                "direct": _t(tx, "ownershipNature/directOrIndirectOwnership"),
            })
    footnotes = [(f.text or "").strip() for f in root.findall("footnotes/footnote")]
    if not plan and any(re.search(r"10b5-1", f, re.I) for f in footnotes):
        plan = True
    return {"owners": owners, "transactions": txs, "plan_10b5_1": plan, "period": _t(root, "periodOfReport")}


_DOC_RE = re.compile(r"<DOCUMENT>(.*?)</DOCUMENT>", re.S | re.I)


def find_exhibit(index_headers_html: str, prefix: str = "EX-99") -> str | None:
    """Filename of the first exhibit whose <TYPE> starts with prefix (EX-99.1 before EX-99.2)."""
    import html as _html

    hits = []
    for block in _DOC_RE.findall(_html.unescape(index_headers_html)):   # SEC escapes the tags in the page body
        t = re.search(r"<TYPE>\s*([^\s<]+)", block, re.I)
        f = re.search(r"<FILENAME>\s*([^\s<]+)", block, re.I)
        if t and f and t.group(1).upper().startswith(prefix):
            hits.append((t.group(1).upper(), f.group(1)))
    hits.sort()
    return hits[0][1] if hits else None


_MONEY_RE = re.compile(r"\$\s?\d[\d,.]*\s?(?:billion|million|thousand)?|\d[\d,.]*\s?%|\d[\d,.]*\s(?:billion|million)", re.I)


def press_release(html: bytes | str, max_highlights: int = 8) -> dict:
    """Lead paragraphs and the sentences carrying the numbers (revenue, EPS, guidance...)."""
    text = extract.html_to_text(html)
    paras = [p.strip() for p in re.split(r"\n\s*\n|\n", text) if len(p.split()) >= 12]
    lead = " ".join(paras[:2])[:900]
    sentences = re.split(r"(?<=[.!?])\s+(?=[A-Z])", " ".join(paras[:60]))
    highlights, seen = [], set()
    for s in sentences:
        s = s.strip()
        if 40 <= len(s) <= 420 and len(_MONEY_RE.findall(s)) >= 2:
            key = s[:80].lower()
            if key not in seen:
                seen.add(key)
                highlights.append(s)
        if len(highlights) >= max_highlights:
            break
    return {"lead": lead, "highlights": highlights}
