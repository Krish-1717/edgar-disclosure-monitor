# EDGAR Disclosure Monitor â Claude Code Master Context

> **Claude Code reads this file automatically every session. Never delete it.**
> Last updated: November 2026

## Second Brain Imports
<!-- Claude Code loads these files into context automatically on every session -->
@/Users/krish/Desktop/Second Brain/CLAUDE.md
@/Users/krish/Desktop/Second Brain/Projects/EDGAR-Monitor/CLAUDE.md

---

## Project Identity
- **What it is:** Single-file HTML/CSS/JS SEC EDGAR filing intelligence dashboard
- **Live URL:** https://htmlpreview.github.io/?https://raw.githubusercontent.com/Krish-1717/edgar-disclosure-monitor/main/frontend/edgar_v2.html
- **GitHub:** https://github.com/Krish-1717/edgar-disclosure-monitor
- **Owner:** Krish Patel â Quant Finance @ Stevens Institute of Technology
- **Second Brain:** ~/Desktop/Second Brain/ â roadmap, bugs, project notes all live there

---

## Repository Structure

```
edgar-disclosure-monitor/
âââ CLAUDE.md              <- YOU ARE HERE (imports Second Brain on load)
âââ .gitignore             <- hides .env
âââ .env.example           <- API key template (safe to commit)
âââ .env                   <- NEVER commit â real keys go here
âââ fix_encoding.py        <- run after every edit to edgar_v2.html
âââ frontend/
    âââ edgar_v2.html      <- THE ENTIRE APP (~78KB, single file)
    âââ index.html
```

No build step, no npm, no framework. The entire app is `frontend/edgar_v2.html`.

---

## API Keys

All secret keys live in `.env` â gitignored, never committed.

```bash
cp .env.example .env   # fill in real values
```

For the frontend: SEC EDGAR APIs need no key (free, CORS allowed).
For v6+ backend: use python-dotenv â `load_dotenv(); os.getenv("OPENAI_API_KEY")`
Never hardcode keys in edgar_v2.html.

---

## CRITICAL RULE #1 â ENCODING FIX

Run after EVERY edit to edgar_v2.html:

```bash
python3 fix_encoding.py
```

Why: htmlpreview.github.io serves without charset=utf-8. Any char with Unicode > 127 inside a script tag corrupts. The script escapes them all as \uXXXX literals.

---

## CRITICAL RULE #2 â GIT WORKFLOW

```bash
python3 fix_encoding.py
git add frontend/edgar_v2.html
git commit -m "feat: your message"
git push origin main
```

After push: hard refresh htmlpreview (Cmd+Shift+R) after ~30 seconds.

---

## App Architecture

### CSS Variables (:root)
- Background: `--bg:#070714` `--bg2:#0d0d1a` `--bg3:#12121f` `--surface:#1a1a2e` `--border:#2a2a4a`
- Accent: `--accent:#6366f1` `--accent2:#818cf8` `--cyan:#22d3ee`
- Status: `--green:#10b981` `--red:#ef4444` `--yellow:#f59e0b`
- Text: `--text:#e2e8f0` `--muted:#6b7280` | Font: Inter (Google Fonts)

### HTML Layout
```
#landing -> hero page (hides on "Open Platform")
#app -> 3-column flex:
  .sidebar(280px) | .main-area(flex-grow:1) | #filing-panel(400px, slides in)
                       |- #graph-svg  D3 force graph
                       +- #ai-chat    sticky bottom chat
```

### JavaScript Sections (order inside edgar_v2.html)
| Section | Key | Purpose |
|---------|-----|---------|
| Ticker DB | `TICKER_DB` | 20 tickers with name, price, change, sector |
| Filing Data | `FILING_DATA` | Per-ticker arrays of filing objects |
| Diffs | `DIFFS` | Before/after text for diff viewer |
| AI Responses | `AI_RESPONSES` | Deterministic responses by topic |
| State | `pinnedStocks`, `activeStock`, `simulation` | App state |
| Navigation | `enterApp()`, `exitApp()` | Landing to dashboard |
| Search | `onSearchInput()`, `addStock()`, `removeStock()`, `selectStock()` | Sidebar |
| Sidebar | `renderSidebar()`, `generateSparkline()` | Stock list |
| D3 Graph | `buildWebTree()`, `getRadius()`, `matColor()` | Force graph |
| Filing Panel | `openFilingPanel()`, `closePanel()`, `switchTab()` | Right panel |
| Crawler Tab | `renderCrawlerTab()` | 16-step typewriter animation |
| Diff Tab | `renderDiffTab()` | Expandable before/after cards |
| Score Tab | `renderScoreTab()` | Animated SVG ring |
| AI Chat | `sendChat()`, `onChatKey()` | Chat panel |

---

## 20-Ticker Database
NVDA, AAPL, MSFT, GOOGL, META, AMZN, TSLA, JPM, BAC, GS, NFLX, LLY, XOM, AMD, NKE, BRKB, V, MA, UNH, PYPL

NVDA has the richest mock data (7 filings, 4 diffs). All others fall back to DEFAULT. Follow NVDA's structure when adding real data.

Filing schema: `{ id, form, date, current, materiality(0-1), group }`
Diff schema: `{ type, label, text, old_text, new_text }`

---

## D3 Force Graph
- Node radius: `8 + materiality * 16` (range 8-24px)
- Node color: `mat>0.75 -> red | mat>0.5 -> yellow | else -> green`
- Forces: link(dist=80), charge(-200), center, collision(radius+8)
- Draggable via d3.drag(), zoomable via d3.zoom() on SVG

---

## Scoring System
| Score | Meaning |
|-------|---------|
| Materiality (0-100) | How significant are the disclosure changes? |
| Burial (0-100) | How buried is key info in footnotes? |
| Attention Gap (0-100) | How much is the market underreacting? |

SVG ring animates 0 to score over 1.2s via requestAnimationFrame.

---

## v5 Real EDGAR APIs (no API key needed)
- CIK lookup: `https://www.sec.gov/files/company_tickers.json`
- Filings: `https://data.sec.gov/submissions/CIK{10-digit-cik}.json`
- Filing docs: `https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/`

CORS is allowed from browsers â no proxy needed.

---

## Open Bugs
| ID | Bug | Fix |
|----|-----|-----|
| BUG-004 | D3 runs after stock removed | `simulation.stop()` in `removeStock()` |
| BUG-005 | Chat textarea grows unbounded | `max-height:120px; overflow-y:auto` on `#chat-input` |
| BUG-006 | Empty SVG when last stock removed | Check `pinnedStocks.length===0`, show empty-state div |

Full history: ~/Desktop/Second Brain/Projects/EDGAR-Monitor/bugs-and-fixes.md

---

## Quick Reference
| Task | Command / Location |
|------|--------------------|
| Edit app | `frontend/edgar_v2.html` |
| Fix encoding | `python3 fix_encoding.py` |
| API keys | `.env` (gitignored), template in `.env.example` |
| Roadmap | ~/Desktop/Second Brain/Projects/EDGAR-Monitor/roadmap.md |
| Bug history | ~/Desktop/Second Brain/Projects/EDGAR-Monitor/bugs-and-fixes.md |
| Add ticker | `TICKER_DB`, `FILING_DATA`, optionally `DIFFS` |
| Add AI topic | Key in `AI_RESPONSES`, keyword in `sendChat()` |
