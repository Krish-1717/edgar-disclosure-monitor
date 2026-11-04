"""ORACLE crawler tests. All HTTP is mocked with respx - no live SEC calls.

Run:  python -m pytest tests/test_oracle.py
"""
from __future__ import annotations

import json
import os
import pathlib
import sys

import httpx
import pytest
import respx

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import oracle_fixtures as fx  # noqa: E402
from oracle import discovery, extract  # noqa: E402
from oracle.cli import main as cli_main  # noqa: E402
from oracle.client import RateLimiter, SecClient, SecHttpError  # noqa: E402
from oracle.config import ConfigError, Settings, parse_forms, validate_user_agent  # noqa: E402
from oracle.crawler import Crawler  # noqa: E402
from oracle.storage import Store  # noqa: E402

ARCH = f"https://www.sec.gov/Archives/edgar/data/{fx.CIK}"


# -- helpers --------------------------------------------------------------------
class FakeClock:
    def __init__(self):
        self.now = 0.0
        self.sleeps: list[float] = []

    def clock(self):
        return self.now

    def sleep(self, s):
        self.sleeps.append(s)
        self.now += s


def make_client(**kw):
    fc = FakeClock()
    client = SecClient(fx.UA, sleep=fc.sleep, clock=fc.clock, **kw)
    return client, fc


def mock_sec(router, extra=(), docs=None):
    router.get(discovery.TICKERS_URL).respond(json=fx.TICKERS)
    router.get(f"https://data.sec.gov/submissions/CIK{fx.CIK:010d}.json").respond(json=fx.submissions(extra))
    docs = docs or {
        "nvda-20250126.htm": fx.TEN_K_HTML.encode(),
        "nvda-20250126a.htm": fx.TEN_K_HTML.encode(),     # identical bytes -> dedupe
        "wk-form4_1.xml": fx.FORM4_XML,
        "nvda-8k.htm": fx.EIGHT_K_HTML,
        "nvda-20250427.htm": fx.TEN_Q_HTML.encode(),
    }
    rows = list(fx.FILINGS) + list(extra)
    for acc, form, _, _, doc, _ in rows:
        nodash = acc.replace("-", "")
        name = doc.rsplit("/", 1)[-1]
        router.get(f"{ARCH}/{nodash}/index.json").respond(json=fx.index_json(nodash, name))
        ctype = "text/xml" if name.endswith(".xml") else "text/html"
        router.get(f"{ARCH}/{nodash}/{name}").respond(content=docs[name], headers={"content-type": ctype})


@pytest.fixture
def env(tmp_path):
    store = Store(tmp_path / "oracle.db")
    client, fc = make_client()
    crawler = Crawler(client, store, tmp_path / "docs")
    yield crawler, store, client, fc, tmp_path
    client.close()
    store.close()


# -- config ---------------------------------------------------------------------
def test_user_agent_validation():
    assert validate_user_agent('"Jane Doe jane@example.com"') == "Jane Doe jane@example.com"
    assert validate_user_agent("ORACLE/0.1 (Jane Doe; jane@example.com)")
    for bad in (None, "", "python-requests/2.0", "jane@example.com"):
        with pytest.raises(ConfigError):
            validate_user_agent(bad)
    with pytest.raises(ConfigError):
        SecClient("python-httpx")


def test_parse_forms_and_rps_ceiling():
    assert parse_forms("10-k, 10-K/A,def 14a") == ("10-K", "DEF 14A")
    assert parse_forms(None)[0] == "10-K"
    with pytest.raises(ConfigError):
        Settings(user_agent=fx.UA, max_rps=11)
    with pytest.raises(ConfigError):
        RateLimiter(max_rps=50)


# -- rate limiting & retries -------------------------------------------------------
def test_rate_limiter_spacing():
    fc = FakeClock()
    rl = RateLimiter(max_rps=10, clock=fc.clock, sleep=fc.sleep)
    for _ in range(11):
        rl.acquire()
    # 11 requests at 10 rps must take at least 1 second of wall time.
    assert fc.now == pytest.approx(1.0)
    assert all(s == pytest.approx(0.1) for s in fc.sleeps)


@respx.mock
def test_retry_on_429_honours_retry_after():
    route = respx.get("https://data.sec.gov/x.json")
    route.side_effect = [httpx.Response(429, headers={"Retry-After": "3"}), httpx.Response(200, json={"ok": 1})]
    client, fc = make_client()
    assert client.get_json("https://data.sec.gov/x.json") == {"ok": 1}
    assert route.call_count == 2
    assert 3.0 in fc.sleeps
    assert route.calls[0].request.headers["User-Agent"] == fx.UA


@respx.mock
def test_retry_on_5xx_with_backoff_then_gives_up():
    route = respx.get("https://data.sec.gov/y.json").respond(503)
    client, fc = make_client(max_retries=3, backoff_base=1.0)
    with pytest.raises(SecHttpError) as ei:
        client.get("https://data.sec.gov/y.json")
    assert ei.value.status == 503
    assert route.call_count == 4
    backoffs = [s for s in fc.sleeps if s >= 1.0]
    assert len(backoffs) == 3 and backoffs[0] < backoffs[1] < backoffs[2]   # exponential


@respx.mock
def test_transport_error_retried_and_4xx_not_retried():
    flaky = respx.get("https://data.sec.gov/z.json")
    flaky.side_effect = [httpx.ConnectError("boom"), httpx.Response(200, json={})]
    client, _ = make_client()
    assert client.get_json("https://data.sec.gov/z.json") == {}
    missing = respx.get("https://www.sec.gov/missing").respond(404)
    with pytest.raises(SecHttpError):
        client.get("https://www.sec.gov/missing")
    assert missing.call_count == 1


# -- discovery ------------------------------------------------------------------
@respx.mock
def test_ticker_resolution():
    respx.get(discovery.TICKERS_URL).respond(json=fx.TICKERS)
    client, _ = make_client()
    r = discovery.TickerResolver(client)
    assert r.resolve("nvda").cik == fx.CIK
    assert r.resolve("BRK.B").cik == 1067983
    assert r.resolve("320193").ticker == "AAPL"
    with pytest.raises(KeyError):
        r.resolve("NOPE")


def test_filing_refs_urls_and_form4_raw_xml():
    refs = discovery.parse_recent_filings(fx.submissions(), fx.CIK)
    by = {r.accession: r for r in refs}
    tenk = by["0001045810-25-000023"]
    assert tenk.primary_doc_url == f"{ARCH}/000104581025000023/nvda-20250126.htm"
    assert tenk.index_url == f"{ARCH}/000104581025000023/index.json"
    f4 = by["0001045810-25-000040"]
    assert f4.raw_primary_document == "wk-form4_1.xml"
    assert discovery.normalize_accession("000104581025000023") == "0001045810-25-000023"


def test_select_and_versions():
    refs = discovery.parse_recent_filings(fx.submissions([fx.AMENDMENT]), fx.CIK)
    sel = discovery.select_filings(refs, ["10-K"])
    assert [r.form for r in sel] == ["10-K/A", "10-K"]
    assert len(discovery.select_filings(refs, ["10-K", "10-Q", "8-K", "4"], since="2025-03-05")) == 3
    v = discovery.assign_versions(refs)
    assert v["0001045810-25-000023"] == (1, None)
    assert v["0001045810-25-000100"] == (2, "0001045810-25-000023")


# -- extraction -----------------------------------------------------------------
def test_10k_segmentation_skips_toc_and_hidden_xbrl():
    secs = {s["key"]: s for s in extract.segment_html(fx.TEN_K_HTML, "10-K")}
    assert list(secs) == ["risk_factors", "mdna", "market_risk", "financial_statements"]
    assert secs["risk_factors"]["text"].startswith("RISK-BODY")
    assert "Unresolved" not in secs["risk_factors"]["text"]
    assert secs["mdna"]["text"].startswith("MDNA-BODY")
    assert "MARKET-BODY" not in secs["mdna"]["text"]
    assert "FIN-BODY" in secs["financial_statements"]["text"]
    assert "None." not in secs["financial_statements"]["text"]
    assert secs["mdna"]["item"] == "Item 7"
    text = extract.html_to_text(fx.TEN_K_HTML)
    assert "hidden xbrl header" not in text
    assert "Item 1. Business" in text      # inline spans joined, nbsp normalised


def test_10q_segmentation_uses_parts():
    secs = {s["key"]: s for s in extract.segment_html(fx.TEN_Q_HTML, "10-Q")}
    assert secs["financial_statements"]["text"].startswith("QFIN-BODY")
    assert secs["mdna"]["text"].startswith("QMDNA-BODY")
    assert secs["market_risk"]["text"].startswith("QMKT-BODY")
    assert secs["risk_factors"]["text"].startswith("QRISK-BODY")
    assert secs["risk_factors"]["item"] == "Part II, Item 1A"
    assert "QLEGAL" not in secs["financial_statements"]["text"]


def test_non_periodic_forms_not_segmented():
    assert extract.segment_html(fx.EIGHT_K_HTML, "8-K") == []


# -- end to end crawl -------------------------------------------------------------
def test_crawl_end_to_end_then_incremental_amendment(env):
    crawler, store, client, fc, tmp = env
    forms = ("10-K", "10-Q", "8-K", "4")
    with respx.mock(assert_all_called=False) as router:
        mock_sec(router)
        [res] = crawler.crawl(["NVDA"], forms)
    assert res.errors == []
    assert res.discovered == 4 and len(res.new) == 4 and res.amendments == []
    assert res.sections == 8          # 4 from the 10-K, 4 from the 10-Q

    tenk = store.get_filing("0001045810-25-000023")
    assert tenk["status"] == "fetched" and tenk["version"] == 1
    docs = store.documents_for(tenk["accession"])
    assert {d["kind"] for d in docs} == {"index", "primary"}
    primary = next(d for d in docs if d["kind"] == "primary")
    assert pathlib.Path(primary["local_path"]).read_bytes() == fx.TEN_K_HTML.encode()
    import hashlib
    assert primary["sha256"] == hashlib.sha256(fx.TEN_K_HTML.encode()).hexdigest() == tenk["sha256"]
    f4 = next(d for d in store.documents_for("0001045810-25-000040") if d["kind"] == "primary")
    assert f4["filename"] == "wk-form4_1.xml"

    # Fair access: tickers + submissions + (index + doc) per filing, spaced >= 1/8 s apart.
    assert client.request_count == 2 + 4 * 2
    assert fc.now >= (client.request_count - 1) * 0.125 - 1e-9

    # Second run: nothing new, only discovery requests.
    with respx.mock(assert_all_called=False) as router:
        mock_sec(router)
        before = client.request_count
        [res2] = crawler.crawl(["NVDA"], forms)
        assert res2.new == [] and client.request_count - before == 1   # tickers cached, submissions only

    # Third run: a 10-K/A appears -> detected as amendment v2, identical doc deduplicated.
    with respx.mock(assert_all_called=False) as router:
        mock_sec(router, extra=[fx.AMENDMENT])
        [res3] = crawler.crawl(["NVDA"], forms)
    assert res3.new == ["0001045810-25-000100"] and res3.amendments == res3.new
    amend = store.get_filing("0001045810-25-000100")
    assert amend["is_amendment"] == 1 and amend["version"] == 2
    assert amend["amends_accession"] == "0001045810-25-000023"
    adoc = next(d for d in store.documents_for(amend["accession"]) if d["kind"] == "primary")
    assert adoc["deduplicated"] == 1 and adoc["local_path"] == primary["local_path"]
    assert len(list((tmp / "docs").rglob("*.htm"))) == 3   # 10-K, 8-K, 10-Q (10-K/A deduped)
    run = store.last_run()
    assert run["new_filings"] == 1 and run["amendments"] == 1


def test_crawl_records_errors_and_retries_next_run(env):
    crawler, store, *_ = env
    with respx.mock(assert_all_called=False) as router:
        mock_sec(router)
        router.get(f"{ARCH}/000104581025000050/nvda-8k.htm").respond(404)
        [res] = crawler.crawl(["NVDA"], ["8-K"])
    assert len(res.errors) == 1 and res.new == []
    assert store.get_filing("0001045810-25-000050")["status"] == "error"
    with respx.mock(assert_all_called=False) as router:
        mock_sec(router)
        [res] = crawler.crawl(["NVDA"], ["8-K"])
    assert res.new == ["0001045810-25-000050"]
    assert store.get_filing("0001045810-25-000050")["status"] == "fetched"


def test_unknown_ticker_is_reported(env):
    crawler, *_ = env
    with respx.mock(assert_all_called=False) as router:
        mock_sec(router)
        [res] = crawler.crawl(["ZZZZ"], ["10-K"])
    assert res.errors and res.cik is None


# -- API -----------------------------------------------------------------------
def test_api(env):
    from fastapi.testclient import TestClient
    from oracle.api import create_app

    crawler, store, _, _, tmp = env
    with respx.mock(assert_all_called=False) as router:
        mock_sec(router, extra=[fx.AMENDMENT])
        crawler.crawl(["NVDA"], ["10-K", "10-Q"])

    app = create_app(store.db_path, cors_origins=["https://krish-1717.github.io"])
    api = TestClient(app)

    r = api.get("/companies/nvda/filings")
    assert r.status_code == 200
    body = r.json()
    assert body["company"]["cik"] == fx.CIK
    assert [f["form"] for f in body["filings"]] == ["10-K/A", "10-Q", "10-K"]
    assert api.get("/companies/NVDA/filings?form=10-Q").json()["count"] == 1
    assert api.get("/companies/MSFT/filings").status_code == 404

    f = api.get("/filings/000104581025000023").json()
    assert f["accession"] == "0001045810-25-000023"
    assert [s["key"] for s in f["sections"]] == ["risk_factors", "mdna", "market_risk", "financial_statements"]
    assert "text" not in f["sections"][0]
    assert f["amendments"][0]["accession"] == "0001045810-25-000100"
    assert {d["kind"] for d in f["documents"]} == {"index", "primary"}
    assert "text" in api.get("/filings/0001045810-25-000023?include_text=true").json()["sections"][0]
    sec = api.get("/filings/0001045810-25-000023/sections/mdna").json()
    assert sec["text"].startswith("MDNA-BODY")
    assert api.get("/filings/not-an-accession").status_code == 422
    assert api.get("/filings/0000000000-00-000000").status_code == 404

    pre = api.options("/companies/NVDA/filings", headers={
        "Origin": "https://krish-1717.github.io", "Access-Control-Request-Method": "GET"})
    assert pre.headers["access-control-allow-origin"] == "https://krish-1717.github.io"
    evil = api.get("/health", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in evil.headers


# -- CLI ------------------------------------------------------------------------
def test_cli_crawl_and_list(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("ORACLE_USER_AGENT", fx.UA)
    monkeypatch.setenv("ORACLE_DATA_DIR", str(tmp_path / "docs"))
    db = tmp_path / "cli.db"
    with respx.mock(assert_all_called=False) as router:
        mock_sec(router)
        rc = cli_main(["--db", str(db), "crawl", "NVDA", "--forms", "10-K,10-Q"])
    out = capsys.readouterr().out
    assert rc == 0, out
    assert "NVDA" in out and "NVIDIA CORP" in out
    assert cli_main(["--db", str(db), "filings", "NVDA"]) == 0
    listing = capsys.readouterr().out
    assert "0001045810-25-000023" in listing and "mdna" in listing


def test_cli_missing_user_agent(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("ORACLE_USER_AGENT", raising=False)
    monkeypatch.delenv("EDGAR_USER_AGENT", raising=False)
    monkeypatch.setattr("oracle.config._load_dotenv", lambda f: None)
    assert cli_main(["--db", str(tmp_path / "x.db"), "crawl", "NVDA"]) == 2
    assert "ORACLE_USER_AGENT" in capsys.readouterr().err
