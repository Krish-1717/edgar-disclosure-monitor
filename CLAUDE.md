# EDGAR Disclosure Monitor - Claude Code Master Context

> **Claude Code reads this file automatically every session. Never delete it.**
> Last updated: 2026-11-04 (website redesign + move to GitHub Pages)

## Second Brain Imports
<!-- Claude Code loads these files into context automatically on every session -->
@/Users/krish/Desktop/Second Brain/CLAUDE.md
@/Users/krish/Desktop/Second Brain/Projects/EDGAR-Monitor/CLAUDE.md

---

## Project Identity
- **What it is:** SEC EDGAR filing intelligence. Static website + demo app (repo root) and a Python backend (repo root `*.py`, untouched by the website).
- **Website:** https://krish-1717.github.io/edgar-disclosure-monitor/ (GitHub Pages, `main` / root)
- **Demo app:** https://krish-1717.github.io/edgar-disclosure-monitor/app.html
- **Old URL:** the htmlpreview.github.io link to `frontend/edgar_v2.html` now redirects to the app. htmlpreview never loaded CDN scripts (D3 was undefined there), which is why the site moved to Pages.
- **GitHub:** https://github.com/Krish-1717/edgar-disclosure-monitor
- **Owner:** Krish Patel - Quant Finance @ Stevens Institute of Technology
- **Long-term vision:** "ORACLE", an institutional-grade SEC crawler + AI engine (Python, Scrapy, EdgarTools, Arelle, FastAPI, PostgreSQL). The website only presents it.

---

## Website Structure (static, no build step, no Node)

```
index.html            landing: scroll-pinned cinematic hero (canvas particles -> hive), pipeline, coverage, ORACLE, CTA
app.html              demo app: watchlist | D3 hive network + crawler strip | analysis panel; AI workspace at bottom
privacy.html          legal TEMPLATE (needs lawyer review)
terms.html            legal TEMPLATE (needs lawyer review)
404.html              self-contained (Pages serves it at any depth; uses absolute URLs)
sitemap.xml robots.txt site.webmanifest .nojekyll
assets/css/site.css   tokens, nav, buttons, glass, modal/form, consent banner, footer, legal pages
assets/css/landing.css / app.css
assets/js/site.js     consent (Consent Mode v2, default denied) + GA4 loader + Web3Forms waitlist modal
assets/js/landing.js  scrollytelling loop (transform/opacity only, rAF, reduced-motion fallback)
assets/js/app.js      mock data + hive graph + panel + workspace
assets/img/           favicon.svg, favicon-32.png, apple-touch-icon.png, icon-192/512.png, og-image.jpg (1200x630), og-image.svg (source)
frontend/edgar_v2.html  redirect stub -> app.html (old single-file app is in git history before the redesign commit)
frontend/index.html, frontend/notifications.js  legacy, not linked from the site
```

## Owner placeholders (in `assets/js/site.js`)
- `GA_MEASUREMENT_ID = 'G-XXXXXXXXXX'` - GA4 only loads after the visitor clicks Accept.
- `WEB3FORMS_ACCESS_KEY = 'YOUR_WEB3FORMS_ACCESS_KEY'` - until set, the form shows "not connected yet".
- Legal pages: `[CONTACT EMAIL]`, `[LEGAL NAME / ENTITY]`, `[DATE]`, jurisdiction, etc.
Both keys are public identifiers, not secrets. Never put real secrets in the frontend.

---

## CRITICAL RULE #1 - ENCODING

All site files are pure ASCII. Use HTML entities in markup and `\uXXXX` inside JS. After every edit:

```bash
python3 fix_encoding.py          # fixes + verifies all site files
python3 fix_encoding.py --check  # verify only
```

## CRITICAL RULE #2 - GIT WORKFLOW

```bash
python3 fix_encoding.py
git add <files>
git commit -m "feat: your message"
git push origin main     # Pages redeploys in ~1 minute
```

## Local preview

```bash
python3 -m http.server 8766 --bind 127.0.0.1   # from repo root, open http://127.0.0.1:8766/
```
(404.html uses absolute live URLs, so its links point at the deployed site.)

---

## Design system
- Dark OLED base `--bg:#05060c`; text `#eef1f8` / `#c0c7d8`; muted `#949db2` (>= 5.9:1 on all surfaces)
- Accents: periwinkle `#a5adff`, teal `#5eead4`, gold `#e3c08a`, rose `#ff9aae`; CTA ivory `#eef0ff` on `#0a0c18`
- Fonts (Google Fonts): Instrument Serif (display), IBM Plex Sans (UI), IBM Plex Mono (data)
- Motion: slow ease-in-out `cubic-bezier(.65,0,.35,1)`; animate transform/opacity only; honor prefers-reduced-motion
- Exactly one CTA on the landing page: "Get early access" (`data-waitlist` opens the modal)

## App data model (`assets/js/app.js`)
| Key | Purpose |
|-----|---------|
| `TICKER_DB` | 20 tickers: name, price, change, sector, cik, exchange |
| `FILING_DATA` | Per-ticker base filings (NVDA rich, others use DEFAULT). Schema `{id, form, date, current, materiality, burial, gap, group}` |
| `getFilings(t)` | Base filings + seeded extras across 7 categories (DEF 14A, Form 4, 13G, S-8, 424B2/FWP, SD...) |
| `DIFFS` | Before/after passages `{type, section, text, before, after}`; `CATEGORY_DIFFS` for non-financial forms |
| `CATEGORIES`, `TIER1` | Filing taxonomy + Tier 1 forms (10-K, 10-Q, 8-K, DEF 14A, Form 4, S-1, S-4) |
| `SHARED_ENTITIES` | Illustrative shared holders / executives / deals linking clusters |
| `AI_RESPONSES` | Deterministic mock chat responses |

Workspace modes: Chat, Research (plan + cited summary), Report (brief + Download .md). Commands: `add NVDA`, `remove NVDA`, `load demo`.
Watchlist persists in localStorage (`edm_watchlist_v1`); `app.html?t=NVDA,MSFT` deep-links a watchlist.

## v5 Real EDGAR APIs (no API key needed)
- CIK lookup: `https://www.sec.gov/files/company_tickers.json`
- Filings: `https://data.sec.gov/submissions/CIK{10-digit-cik}.json`
- Filing docs: `https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/`
Note: verify CORS from the deployed origin before relying on direct browser calls; a small backend proxy (FastAPI) may be needed. SEC also requires a descriptive User-Agent for automated access.

## API keys
Backend secrets live in `.env` (gitignored); template in `.env.example`. Use python-dotenv. Never hardcode keys in the frontend.

Full history: ~/Desktop/Second Brain/Projects/EDGAR-Monitor/bugs-and-fixes.md
