"""ORACLE - SEC EDGAR crawler (v0).

Pipeline: discovery (ticker -> CIK -> submissions) -> retrieval (primary
document + filing index, fair-access rate limited, SHA-256 dedupe) ->
storage (SQLite, PostgreSQL-ready schema) -> extraction (10-K / 10-Q
section segmentation) -> FastAPI read API.

Run ``python -m oracle --help`` for the CLI.
"""

__version__ = "0.1.0"

TIER1_FORMS = ("10-K", "10-Q", "8-K", "DEF 14A", "4", "S-1", "S-4")
