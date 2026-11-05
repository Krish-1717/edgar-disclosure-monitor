"""Discovery: ticker -> CIK, submissions -> filing references, amendment versioning."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
TICKERS_EXCHANGE_URL = "https://www.sec.gov/files/company_tickers_exchange.json"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
ARCHIVES_URL = "https://www.sec.gov/Archives/edgar/data"

_ACCESSION_RE = re.compile(r"^(\d{10})-?(\d{2})-?(\d{6})$")


def normalize_accession(value: str) -> str:
    """'000104581025000023' or '0001045810-25-000023' -> '0001045810-25-000023'."""
    m = _ACCESSION_RE.match(value.strip())
    if not m:
        raise ValueError(f"not an accession number: {value!r}")
    return "-".join(m.groups())


def normalize_ticker(ticker: str) -> str:
    return ticker.strip().upper().replace(".", "-")


def base_form(form: str) -> str:
    form = form.strip().upper()
    return form[:-2] if form.endswith("/A") else form


@dataclass(frozen=True)
class Company:
    cik: int
    ticker: str
    name: str


@dataclass(frozen=True)
class FilingRef:
    accession: str
    cik: int
    form: str
    filing_date: str
    report_date: str
    acceptance_datetime: str
    primary_document: str
    primary_doc_description: str = ""
    items: str = ""          # 8-K item numbers, e.g. "2.02,9.01"
    size: int = 0

    @property
    def base_form(self) -> str:
        return base_form(self.form)

    @property
    def is_amendment(self) -> bool:
        return self.form.strip().upper().endswith("/A")

    @property
    def accession_nodash(self) -> str:
        return self.accession.replace("-", "")

    @property
    def folder_url(self) -> str:
        return f"{ARCHIVES_URL}/{self.cik}/{self.accession_nodash}"

    @property
    def raw_primary_document(self) -> str:
        """Form 3/4/5 list an XSL-rendered path ('xslF345X05/doc.xml'); keep the raw XML."""
        doc = self.primary_document
        if "/" in doc and doc.split("/", 1)[0].lower().startswith("xsl"):
            return doc.rsplit("/", 1)[-1]
        return doc

    @property
    def primary_doc_url(self) -> str:
        return f"{self.folder_url}/{self.raw_primary_document}"

    @property
    def index_url(self) -> str:
        """Machine-readable filing index (directory listing)."""
        return f"{self.folder_url}/index.json"

    @property
    def index_htm_url(self) -> str:
        return f"{self.folder_url}/{self.accession}-index.htm"


class TickerResolver:
    """Resolve tickers (or numeric CIKs) via SEC's company_tickers.json."""

    def __init__(self, client):
        self._client = client
        self._by_ticker: dict[str, Company] | None = None
        self._by_cik: dict[int, Company] = {}

    def _load(self) -> dict[str, Company]:
        if self._by_ticker is None:
            data = self._client.get_json(TICKERS_URL)
            rows = data.values() if isinstance(data, dict) else data
            by_ticker: dict[str, Company] = {}
            for row in rows:
                c = Company(int(row["cik_str"]), normalize_ticker(row["ticker"]), row["title"])
                by_ticker.setdefault(c.ticker, c)
                self._by_cik.setdefault(c.cik, c)
            self._by_ticker = by_ticker
        return self._by_ticker

    def resolve(self, ticker_or_cik: str) -> Company:
        table = self._load()
        key = ticker_or_cik.strip()
        if key.isdigit():
            cik = int(key)
            return self._by_cik.get(cik, Company(cik, key, ""))
        t = normalize_ticker(key)
        if t not in table:
            raise KeyError(f"unknown ticker: {ticker_or_cik}")
        return table[t]


def fetch_submissions(client, cik: int) -> dict:
    return client.get_json(SUBMISSIONS_URL.format(cik=cik))


def parse_recent_filings(submissions: dict, cik: int | None = None) -> list[FilingRef]:
    """Turn the columnar ``filings.recent`` block into FilingRef rows."""
    cik = int(cik if cik is not None else submissions["cik"])
    recent = submissions.get("filings", {}).get("recent", {})
    accessions = recent.get("accessionNumber", [])

    def col(name, i, default=""):
        values = recent.get(name) or []
        return values[i] if i < len(values) and values[i] is not None else default

    refs = []
    for i, acc in enumerate(accessions):
        refs.append(FilingRef(
            accession=normalize_accession(acc),
            cik=cik,
            form=str(col("form", i)),
            filing_date=str(col("filingDate", i)),
            report_date=str(col("reportDate", i)),
            acceptance_datetime=str(col("acceptanceDateTime", i)),
            primary_document=str(col("primaryDocument", i)),
            primary_doc_description=str(col("primaryDocDescription", i)),
            items=str(col("items", i)),
            size=int(col("size", i, 0) or 0),
        ))
    return refs


def select_filings(
    refs: Iterable[FilingRef],
    forms: Iterable[str],
    since: str | None = None,
    limit: int | None = None,
) -> list[FilingRef]:
    """Filter to the requested base forms (amendments included), newest first."""
    wanted = {base_form(f) for f in forms}
    out = [
        r for r in refs
        if r.base_form in wanted and r.primary_document and (not since or r.filing_date >= since)
    ]
    out.sort(key=lambda r: (r.filing_date, r.acceptance_datetime, r.accession), reverse=True)
    return out[:limit] if limit else out


def assign_versions(refs: Iterable[FilingRef]) -> dict[str, tuple[int, str | None]]:
    """accession -> (version, amends_accession).

    Originals are version 1. An amendment ``X/A`` is matched to the original
    ``X`` with the same report period (falling back to the latest original
    filed before it) and numbered 2, 3, ... in filing order. Best effort:
    EDGAR does not publish an explicit amendment link.
    """
    ordered = sorted(refs, key=lambda r: (r.filing_date, r.acceptance_datetime, r.accession))
    result: dict[str, tuple[int, str | None]] = {}
    originals: list[FilingRef] = []
    amend_counts: dict[str, int] = {}
    for r in ordered:
        if not r.is_amendment:
            originals.append(r)
            result[r.accession] = (1, None)
            continue
        same_form = [o for o in originals if o.base_form == r.base_form]
        target = None
        if r.report_date:
            same_period = [o for o in same_form if o.report_date == r.report_date]
            target = same_period[-1] if same_period else None
        if target is None and same_form:
            target = same_form[-1]
        key = target.accession if target else f"orphan:{r.base_form}:{r.report_date}"
        amend_counts[key] = amend_counts.get(key, 0) + 1
        result[r.accession] = (1 + amend_counts[key], target.accession if target else None)
    return result
