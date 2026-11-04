"""Read-only FastAPI app over the ORACLE store.

    uvicorn oracle.api:app --reload      # or: python -m oracle serve
"""
from __future__ import annotations

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from . import __version__
from .config import Settings
from .discovery import normalize_accession
from .export import build_company_feed
from .storage import Store


def _filing_summary(row: dict) -> dict:
    return {
        "accession": row["accession"],
        "form": row["form"],
        "base_form": row["base_form"],
        "is_amendment": bool(row["is_amendment"]),
        "version": row["version"],
        "amends_accession": row["amends_accession"],
        "filing_date": row["filing_date"],
        "report_date": row["report_date"],
        "acceptance_datetime": row["acceptance_datetime"],
        "items": row["items"].split(",") if row["items"] else [],
        "primary_doc_url": row["primary_doc_url"],
        "index_url": row["index_url"],
        "sha256": row["sha256"],
        "status": row["status"],
    }


def create_app(db_path=None, cors_origins=None) -> FastAPI:
    settings = Settings.from_env()
    store = Store(db_path or settings.db_path)
    origins = list(cors_origins if cors_origins is not None else settings.cors_origins)

    app = FastAPI(title="ORACLE SEC filings API", version=__version__)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_methods=["GET"],
        allow_headers=["*"],
    )
    app.state.store = store

    @app.get("/health")
    def health():
        return {"status": "ok", "version": __version__, "last_run": store.last_run()}

    @app.get("/companies")
    def companies():
        return {"companies": store.list_companies()}

    @app.get("/companies/{ticker}/feed")
    def company_feed(ticker: str, limit: int = Query(100, ge=1, le=500)):
        """Same payload the static export writes to companies/{TICKER}.json."""
        feed = build_company_feed(store, ticker, limit=limit)
        if not feed:
            raise HTTPException(404, f"{ticker.upper()} has not been crawled yet")
        return feed

    @app.get("/companies/{ticker}/filings")
    def company_filings(
        ticker: str,
        form: str | None = Query(None, description="Base form, e.g. 10-K (amendments included)"),
        limit: int = Query(50, ge=1, le=500),
        offset: int = Query(0, ge=0),
    ):
        company = store.get_company(ticker)
        if not company:
            raise HTTPException(404, f"{ticker.upper()} has not been crawled yet")
        rows = store.list_filings(company["cik"], form=form, limit=limit, offset=offset)
        return {
            "company": {k: company[k] for k in ("cik", "ticker", "name", "last_crawled_at")},
            "count": len(rows),
            "filings": [_filing_summary(r) for r in rows],
        }

    def _lookup(accession: str) -> dict:
        try:
            acc = normalize_accession(accession)
        except ValueError:
            raise HTTPException(422, "accession must look like 0001045810-25-000023")
        row = store.get_filing(acc)
        if not row:
            raise HTTPException(404, f"filing {acc} not found")
        return row

    @app.get("/filings/{accession}")
    def filing(accession: str, include_text: bool = False):
        row = _lookup(accession)
        out = _filing_summary(row)
        out["cik"] = row["cik"]
        out["error"] = row["error"]
        out["amendments"] = store.amendments_of(row["accession"])
        out["documents"] = [
            {k: d[k] for k in ("kind", "filename", "url", "sha256", "size_bytes", "content_type", "deduplicated")}
            for d in store.documents_for(row["accession"])
        ]
        out["sections"] = store.sections_for(row["accession"], include_text=include_text)
        return out

    @app.get("/filings/{accession}/sections/{key}")
    def filing_section(accession: str, key: str):
        row = _lookup(accession)
        sec = store.get_section(row["accession"], key)
        if not sec:
            raise HTTPException(404, f"section {key!r} not found for {row['accession']}")
        return sec

    return app


def __getattr__(name):   # lazy so importing the module doesn't open the DB
    if name == "app":
        return create_app()
    raise AttributeError(name)
