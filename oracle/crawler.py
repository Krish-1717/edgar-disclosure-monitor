"""Crawl orchestration: discovery -> retrieval -> storage -> extraction."""
from __future__ import annotations

import hashlib
import json
import logging
import pathlib
import re
from dataclasses import dataclass, field

from . import discovery, extract
from .client import SecHttpError
from .storage import Store

log = logging.getLogger(__name__)

_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9._-]+")
EXTRACT_FORMS = {"10-K", "10-Q"}


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@dataclass
class TickerResult:
    ticker: str
    cik: int | None = None
    name: str = ""
    discovered: int = 0          # matching filings listed in submissions
    new: list[str] = field(default_factory=list)          # accessions fetched this run
    amendments: list[str] = field(default_factory=list)   # subset of new that are /A
    deduplicated: int = 0
    sections: int = 0
    errors: list[str] = field(default_factory=list)


class Crawler:
    def __init__(self, client, store: Store, data_dir: str | pathlib.Path, extract_sections: bool = True):
        self.client = client
        self.store = store
        self.data_dir = pathlib.Path(data_dir)
        self.extract_sections = extract_sections
        self.resolver = discovery.TickerResolver(client)

    # -- public ----------------------------------------------------------------
    def crawl(self, tickers: list[str], forms, since: str | None = None,
              limit: int | None = None, refresh: bool = False) -> list[TickerResult]:
        forms = tuple(forms)
        run_id = self.store.start_run(tickers, forms)
        start_requests = getattr(self.client, "request_count", 0)
        results = [self.crawl_ticker(t, forms, since=since, limit=limit, refresh=refresh) for t in tickers]
        self.store.finish_run(
            run_id,
            discovered=sum(r.discovered for r in results),
            new_filings=sum(len(r.new) for r in results),
            amendments=sum(len(r.amendments) for r in results),
            errors=sum(len(r.errors) for r in results),
            request_count=getattr(self.client, "request_count", 0) - start_requests,
        )
        return results

    def crawl_ticker(self, ticker: str, forms, since: str | None = None,
                     limit: int | None = None, refresh: bool = False) -> TickerResult:
        result = TickerResult(ticker=discovery.normalize_ticker(ticker))
        try:
            company = self.resolver.resolve(ticker)
            result.cik, result.name = company.cik, company.name
            subs = discovery.fetch_submissions(self.client, company.cik)
        except (KeyError, SecHttpError) as exc:
            result.errors.append(str(exc))
            log.error("%s: %s", ticker, exc)
            return result

        name = subs.get("name") or company.name
        result.name = name
        self.store.upsert_company(company.cik, company.ticker, name)

        refs = discovery.parse_recent_filings(subs, company.cik)
        versions = discovery.assign_versions(refs)
        selected = discovery.select_filings(refs, forms, since=since, limit=limit)
        result.discovered = len(selected)

        done = set() if refresh else self.store.fetched_accessions(company.cik)
        todo = [r for r in selected if r.accession not in done]
        # Oldest first, so originals are stored before their amendments.
        for ref in reversed(todo):
            version, amends = versions.get(ref.accession, (1, None))
            self.store.upsert_filing(ref, version, amends)
            try:
                self._fetch_filing(ref, result)
            except (SecHttpError, OSError) as exc:
                self.store.mark_error(ref.accession, str(exc))
                result.errors.append(f"{ref.accession}: {exc}")
                log.error("%s %s: %s", ticker, ref.accession, exc)
                continue
            result.new.append(ref.accession)
            if ref.is_amendment:
                result.amendments.append(ref.accession)
        self.store.touch_company(company.cik)
        return result

    # -- retrieval -----------------------------------------------------------------
    def _store_document(self, ref, kind: str, url: str, data: bytes, content_type: str | None,
                        result: TickerResult) -> tuple[str, str]:
        digest = sha256_hex(data)
        existing = self.store.find_document_by_sha(digest)
        filename = _SAFE_NAME_RE.sub("_", url.rsplit("/", 1)[-1]) or kind
        if existing and pathlib.Path(existing["local_path"]).exists():
            local_path, dedup = existing["local_path"], True
            result.deduplicated += 1
        else:
            folder = self.data_dir / str(ref.cik) / ref.accession_nodash
            folder.mkdir(parents=True, exist_ok=True)
            path = folder / filename
            path.write_bytes(data)
            local_path, dedup = str(path), False
        self.store.add_document(ref.accession, kind, filename, url, local_path, digest,
                                len(data), content_type, dedup)
        return digest, local_path

    def _fetch_filing(self, ref, result: TickerResult) -> None:
        # Filing index (directory listing) - lists every exhibit and XBRL file.
        idx = self.client.get(ref.index_url)
        idx_bytes = json.dumps(idx.json(), indent=1, sort_keys=True).encode()
        self._store_document(ref, "index", ref.index_url, idx_bytes, "application/json", result)

        doc = self.client.get(ref.primary_doc_url)
        ctype = doc.headers.get("content-type")
        digest, _ = self._store_document(ref, "primary", ref.primary_doc_url, doc.content, ctype, result)
        self.store.mark_fetched(ref.accession, digest)

        if self.extract_sections and ref.base_form in EXTRACT_FORMS and _looks_like_html(ref, ctype):
            sections = extract.segment_html(doc.content, ref.form)
            self.store.save_sections(ref.accession, sections)
            result.sections += len(sections)
            if not sections:
                log.warning("%s %s: no sections found", ref.form, ref.accession)


def _looks_like_html(ref, content_type: str | None) -> bool:
    name = ref.raw_primary_document.lower()
    return name.endswith((".htm", ".html")) or "html" in (content_type or "")
