"""Synthetic SEC payloads for the ORACLE tests (no live SEC calls)."""
from __future__ import annotations

import copy

UA = "ORACLE Tests tests@example.com"
CIK = 1045810
TICKERS = {
    "0": {"cik_str": CIK, "ticker": "NVDA", "title": "NVIDIA CORP"},
    "1": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."},
    "2": {"cik_str": 1067983, "ticker": "BRK-B", "title": "BERKSHIRE HATHAWAY INC"},
}

FILINGS = [
    # accession, form, filingDate, reportDate, primaryDocument, items
    ("0001045810-25-000023", "10-K", "2025-02-26", "2025-01-26", "nvda-20250126.htm", ""),
    ("0001045810-25-000040", "4", "2025-03-03", "2025-02-28", "xslF345X05/wk-form4_1.xml", ""),
    ("0001045810-25-000050", "8-K", "2025-03-10", "2025-03-07", "nvda-8k.htm", "5.02,9.01"),
    ("0001045810-25-000090", "10-Q", "2025-05-28", "2025-04-27", "nvda-20250427.htm", ""),
]
AMENDMENT = ("0001045810-25-000100", "10-K/A", "2025-06-02", "2025-01-26", "nvda-20250126a.htm", "")


def submissions(extra=()):
    rows = sorted(list(FILINGS) + list(extra), key=lambda r: r[2], reverse=True)   # SEC lists newest first
    cols = {k: [] for k in ("accessionNumber", "form", "filingDate", "reportDate", "acceptanceDateTime",
                            "primaryDocument", "primaryDocDescription", "items", "size")}
    for acc, form, fdate, rdate, doc, items in rows:
        cols["accessionNumber"].append(acc)
        cols["form"].append(form)
        cols["filingDate"].append(fdate)
        cols["reportDate"].append(rdate)
        cols["acceptanceDateTime"].append(f"{fdate}T16:05:00.000Z")
        cols["primaryDocument"].append(doc)
        cols["primaryDocDescription"].append(form)
        cols["items"].append(items)
        cols["size"].append(1000)
    return copy.deepcopy({"cik": str(CIK), "name": "NVIDIA CORP", "tickers": ["NVDA"],
                          "filings": {"recent": cols, "files": []}})


def _p(text):
    return f"<p>{text}</p>"


LOREM = ("The Company operates in a rapidly evolving industry and faces significant competition, "
         "supply constraints and regulatory uncertainty that could adversely affect results. ") * 6

TEN_K_HTML = f"""<html><head><title>10-K</title><style>.x{{}}</style></head><body>
<div style="display:none"><ix:header>hidden xbrl header Item 7 junk</ix:header></div>
<table>
<tr><td>Item 1.</td><td>Business</td><td>4</td></tr>
<tr><td>Item 1A.</td><td>Risk Factors</td><td>12</td></tr>
<tr><td>Item 7.</td><td>Management&#8217;s Discussion and Analysis</td><td>40</td></tr>
<tr><td>Item 7A.</td><td>Market Risk</td><td>55</td></tr>
<tr><td>Item 8.</td><td>Financial Statements</td><td>56</td></tr>
</table>
<div><span style="font-weight:bold">PART I</span></div>
<div><span>Item</span><span>&#160;1.</span> <span>Business</span></div>
{_p("NVIDIA pioneered accelerated computing. " + LOREM)}
<div><span style="font-weight:bold">Item 1A. Risk Factors</span></div>
{_p("RISK-BODY " + LOREM)}
{_p("Refer to the discussion in our MD&amp;A for more detail on these risks. " + LOREM)}
<div>Item 1B. Unresolved Staff Comments</div>
{_p("None.")}
<div>PART II</div>
<div>Item 7. Management&#8217;s Discussion and Analysis of Financial Condition</div>
{_p("MDNA-BODY Revenue grew 114% driven by Data Center. " + LOREM)}
<div>Item 7A. Quantitative and Qualitative Disclosures About Market Risk</div>
{_p("MARKET-BODY Interest rate risk and foreign exchange risk. " + LOREM)}
<div>Item 8. Financial Statements and Supplementary Data</div>
<table><tr><td>FIN-BODY Revenue</td><td>$130,497</td></tr><tr><td>Net income</td><td>$72,880</td></tr></table>
{_p("Notes to the consolidated financial statements. " + LOREM)}
<div>Item 9. Changes in and Disagreements With Accountants</div>
{_p("None.")}
</body></html>"""

TEN_Q_HTML = f"""<html><body>
<div>PART I. FINANCIAL INFORMATION</div><div>Item 1. Financial Statements (page 3)</div>
<div>Item 2. MD&amp;A (page 20)</div>
<div>PART II. OTHER INFORMATION</div><div>Item 1. Legal Proceedings (page 40)</div><div>Item 1A. Risk Factors (page 41)</div>
<div>PART I. FINANCIAL INFORMATION</div>
<div>Item 1. Financial Statements</div>
{_p("QFIN-BODY Condensed consolidated statements of income. " + LOREM)}
<div>Item 2. Management's Discussion and Analysis of Financial Condition and Results of Operations</div>
{_p("QMDNA-BODY First quarter revenue was a record. " + LOREM)}
<div>Item 3. Quantitative and Qualitative Disclosures About Market Risk</div>
{_p("QMKT-BODY No material changes. " + LOREM)}
<div>Item 4. Controls and Procedures</div>
{_p("Disclosure controls were effective. " + LOREM)}
<div>PART II. OTHER INFORMATION</div>
<div>Item 1. Legal Proceedings</div>
{_p("QLEGAL-BODY Refer to Note 13. " + LOREM)}
<div>Item 1A. Risk Factors</div>
{_p("QRISK-BODY Export controls may restrict sales. " + LOREM)}
<div>Item 2. Unregistered Sales of Equity Securities</div>
{_p("Share repurchases. " + LOREM)}
</body></html>"""

FORM4_XML = b"<?xml version='1.0'?><ownershipDocument><issuer><issuerCik>0001045810</issuerCik></issuer></ownershipDocument>"
EIGHT_K_HTML = b"<html><body><p>Item 5.02 Departure of Directors</p></body></html>"


def index_json(acc_nodash: str, name: str) -> dict:
    return {"directory": {"name": f"/Archives/edgar/data/{CIK}/{acc_nodash}",
                          "item": [{"name": name, "type": "text.gif", "size": "1000"}]}}
