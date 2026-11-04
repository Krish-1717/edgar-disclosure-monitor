# EDGAR Disclosure Monitor â Claude Code Master Context

> Claude Code reads this file automatically every session. Never delete it.
> Last updated: November 2026

---

## Project Identity
- **What it is:** A single-file HTML/CSS/JS SEC EDGAR filing intelligence dashboard
- **Live URL:** https://htmlpreview.github.io/?https://raw.githubusercontent.com/Krish-1717/edgar-disclosure-monitor/main/frontend/edgar_v2.html
- **GitHub:** https://github.com/Krish-1717/edgar-disclosure-monitor
- **Owner:** Krish Patel (patelkrish1717@gmail.com) â Quant Finance @ Stevens Institute of Technology

---

## Repository Structure

```
edgar-disclosure-monitor/
âââ CLAUDE.md              <- YOU ARE HERE â read this first every session
âââ README.md
âââ frontend/
    âââ edgar_v2.html      <- THE ENTIRE APP (single file, ~78KB)
    âââ index.html         <- landing redirect (optional)
```

**There is no build step, no npm, no framework.** The entire app is `frontend/edgar_v2.html`.

---

## CRITICAL RULE #1 â ENCODING FIX (run this after EVERY edit)

**Problem:** htmlpreview.github.io serves without `charset=utf-8`. Any non-ASCII character (em-dash, curly quote, arrow, bullet, any char with Unicode > 127) inside a `<script>` tag gets corrupted into `Ã¢` garbage in the browser.

**Rule:** ALL non-ASCII characters inside `<script>` tags MUST be escaped as `\uXXXX` unicode escapes before committing.

**Run this Python script after every edit to `edgar_v2.html`:**

```python
import re

with open('frontend/edgar_v2.html', 'r', encoding='utf-8') as f:
    content = f.read()

def escape_script(m):
    text = m.group(1)
    result = []
    for ch in text:
        if ord(ch) > 127:
            result.append('\\u{:04x}'.format(ord(ch)))
        else:
            result.append(ch)
    return '<script>' + ''.join(result) + '</script>'

fixed = re.sub(r'<script>(.*?)</script>', escape_script, content, flags=re.DOTALL)

with open('frontend/edgar_v2.html', 'w', encoding='utf-8') as f:
    f.write(fixed)

print('Done. File size:', len(fixed), 'bytes')
```

**Verification command:**
```python
import re
with open('frontend/edgar_v2.html', 'r', encoding='utf-8') as f:
    content = f.read()
for m in re.finditer(r'<script>(.*?)</script>', content, re.DOTALL):
    for i, ch in enumerate(m.group(1)):
        if ord(ch) > 127:
            print(f'BAD char at pos {i}: {ch!r} (U+{ord(ch):04X})')
print('Verification complete.')
```

---

## CRITICAL RULE #2 â HOW TO DEPLOY (upload to GitHub)

The app is deployed via htmlpreview.github.io, which serves raw GitHub files. No CI/CD.

### Option A â Git CLI (preferred when SSH is set up)
```bash
# Run encoding fix first
python3 fix_encoding.py

# Then commit and push
git add frontend/edgar_v2.html
git commit -m "describe your change here"
git push origin main
```

### Option B â GitHub Web Editor (chunked base64 â use when no git access)
This is for when Claude Code can't push via git directly. Use the browser:

```python
# Step 1: Convert file to base64 chunks
import base64

with open('frontend/edgar_v2.html', 'rb') as f:
    data = base64.b64encode(f.read()).decode('ascii')

chunk_size = 7000
chunks = [data[i:i+chunk_size] for i in range(0, len(data), chunk_size)]
print(f'Total b64 length: {len(data)}, chunks: {len(chunks)}')
for i, chunk in enumerate(chunks):
    print(f'--- CHUNK {i} ---')
    print(chunk)
```

```javascript
// Step 2: In browser console at github.com/.../edit/main/frontend/edgar_v2.html
// Inject each chunk:
window._b64 = 'CHUNK_0_HERE';
window._b64 += 'CHUNK_1_HERE';
// ... continue for all chunks ...

// Step 3: Paste into editor
const content = atob(window._b64);
const editorEl = document.querySelector('.cm-editor .cm-content');
editorEl.focus();
document.execCommand('selectAll');
const dt = new DataTransfer();
dt.setData('text/plain', content);
editorEl.dispatchEvent(new ClipboardEvent('paste', { clipboardData: dt, bubbles: true }));
```

---

## App Architecture

### CSS Design System (at `:root`)
```css
--bg: #070714          /* main background */
--bg2: #0d0d1a         /* slightly lighter */
--bg3: #12121f         /* card backgrounds */
--surface: #1a1a2e     /* elevated surfaces */
--border: #2a2a4a      /* borders */
--accent: #6366f1      /* indigo â primary CTA */
--accent2: #818cf8     /* lighter indigo */
--cyan: #22d3ee        /* data/metrics */
--green: #10b981       /* positive / up */
--red: #ef4444         /* negative / alerts */
--yellow: #f59e0b      /* warning / medium */
--text: #e2e8f0        /* primary text */
--muted: #6b7280       /* secondary text */
/* Font: Inter from Google Fonts */
```

### HTML Page Structure
```html
<div id="landing">   <!-- Hero landing page, hidden after user clicks "Open Platform" -->
<div id="app">       <!-- Full dashboard (flex row) -->
  <div class="sidebar">    <!-- 280px fixed left -->
  <div class="main-area">  <!-- flex-grow: 1, center -->
    <svg id="graph-svg">   <!-- D3 force graph -->
    <div id="ai-chat">     <!-- sticky bottom AI chat panel -->
  <div id="filing-panel">  <!-- 400px slides in from right -->
```

### JavaScript Sections (in order inside edgar_v2.html)

| Section | Variable/Function | Purpose |
|---------|------------------|---------|
| Ticker DB | `TICKER_DB` | 20 tickers with name, price, change, sector |
| Filing Data | `FILING_DATA` | Per-ticker arrays of filing objects |
| Diffs | `DIFFS` | Before/after text for diff viewer |
| AI Responses | `AI_RESPONSES` | Response functions keyed by topic |
| State | `pinnedStocks`, `activeStock`, `activeFilingNode`, `simulation` | App state |
| Navigation | `enterApp()`, `exitApp()` | Landing â dashboard |
| Search | `onSearchInput()`, `addStock()`, `removeStock()`, `selectStock()` | Sidebar search |
| Sidebar | `renderSidebar()`, `generateSparkline()` | Stock list rendering |
| D3 Graph | `buildWebTree()`, `getRadius()`, `matColor()`, `animateCrawlerSpider()` | Force graph |
| Filing Panel | `openFilingPanel()`, `closePanel()`, `switchTab()` | Right panel |
| Crawler Tab | `renderCrawlerTab()` | 16-step typewriter log animation |
| Diff Tab | `renderDiffTab()` | Expandable before/after cards |
| Score Tab | `renderScoreTab()` | Animated SVG ring + 3 score badges |
| AI Chat | `sendChat()`, `onChatKey()` | Chat panel |

---

## 20-Ticker Database

```javascript
const TICKER_DB = {
  NVDA: { name: 'NVIDIA Corporation', price: 875.40, change: +3.21, sector: 'Technology' },
  AAPL: { name: 'Apple Inc.', price: 189.30, change: -0.54, sector: 'Technology' },
  MSFT: { name: 'Microsoft Corporation', price: 415.20, change: +1.87, sector: 'Technology' },
  GOOGL: { name: 'Alphabet Inc.', price: 175.80, change: +2.14, sector: 'Technology' },
  META: { name: 'Meta Platforms Inc.', price: 512.60, change: +4.33, sector: 'Technology' },
  AMZN: { name: 'Amazon.com Inc.', price: 185.70, change: +1.56, sector: 'Consumer Discretionary' },
  TSLA: { name: 'Tesla Inc.', price: 248.50, change: -2.87, sector: 'Consumer Discretionary' },
  JPM: { name: 'JPMorgan Chase & Co.', price: 198.40, change: +0.92, sector: 'Financials' },
  BAC: { name: 'Bank of America Corp.', price: 36.80, change: +0.34, sector: 'Financials' },
  GS: { name: 'Goldman Sachs Group Inc.', price: 452.30, change: +2.18, sector: 'Financials' },
  NFLX: { name: 'Netflix Inc.', price: 628.90, change: +5.44, sector: 'Communication Services' },
  LLY: { name: 'Eli Lilly and Company', price: 782.60, change: +3.75, sector: 'Healthcare' },
  XOM: { name: 'Exxon Mobil Corporation', price: 112.40, change: -0.87, sector: 'Energy' },
  AMD: { name: 'Advanced Micro Devices', price: 168.70, change: +2.93, sector: 'Technology' },
  NKE: { name: 'Nike Inc.', price: 94.20, change: -1.23, sector: 'Consumer Discretionary' },
  BRKB: { name: 'Berkshire Hathaway B', price: 368.50, change: +0.45, sector: 'Financials' },
  V: { name: 'Visa Inc.', price: 278.90, change: +1.67, sector: 'Financials' },
  MA: { name: 'Mastercard Incorporated', price: 462.80, change: +2.34, sector: 'Financials' },
  UNH: { name: 'UnitedHealth Group Inc.', price: 548.30, change: -0.98, sector: 'Healthcare' },
  PYPL: { name: 'PayPal Holdings Inc.', price: 68.40, change: +1.12, sector: 'Financials' }
};
```

**NVDA has the richest mock data** (7 filings, 4 diffs, full AI responses). All other tickers fall back to DEFAULT data. When adding real data, follow NVDA's structure exactly.

### Filing Object Schema
```javascript
{
  id: 'NVDA-10K-2024',      // unique string ID
  form: '10-K',              // SEC form type
  date: '2024-02-21',        // filing date ISO string
  current: true,             // is this the most recent?
  materiality: 0.87,         // 0-1 float, drives node color + size in D3
  group: 'annual'            // 'annual' | 'quarterly' | 'amendment' | 'proxy'
}
```

### Diff Object Schema
```javascript
{
  type: 'revenue',           // 'revenue' | 'risk' | 'guidance' | 'legal' | 'other'
  label: 'Revenue Forecast', // display label
  text: 'Short summary...',  // one-liner shown in collapsed card
  old_text: 'Old language from previous filing...',
  new_text: 'New language from current filing...'
}
```

---

## D3 Force Graph Details

```javascript
// Node radius based on materiality score
function getRadius(d) {
  return 8 + d.materiality * 16; // range: 8â24px
}

// Node color based on materiality
function matColor(mat) {
  if (mat > 0.75) return 'var(--red)';    // high â red
  if (mat > 0.50) return 'var(--yellow)'; // medium â yellow
  return 'var(--green)';                   // low â green
}

// D3 simulation forces
d3.forceSimulation(nodes)
  .force('link', d3.forceLink(links).distance(80).strength(0.5))
  .force('charge', d3.forceManyBody().strength(-200))
  .force('center', d3.forceCenter(width/2, height/2))
  .force('collision', d3.forceCollide().radius(d => getRadius(d) + 8))
```

Nodes are draggable via `d3.drag()`. The graph is zoomable via `d3.zoom()` on the SVG container.

---

## Scoring System

| Score | Range | Description |
|-------|-------|-------------|
| Materiality Score | 0â100 | How significant are the changes? Based on keyword frequency delta in key sections |
| Burial Score | 0â100 | How buried are changes? Long filings with key info deep in footnotes score higher |
| Attention Gap | 0â100 | How much is market underreacting? Gap between materiality and analyst coverage change |

The SVG ring animates from 0 to the score value over 1.2 seconds using `requestAnimationFrame`.

---

## AI Chat System

The chat uses a streaming typewriter effect to simulate real AI responses. It is NOT connected to a real API â responses are deterministic functions in `AI_RESPONSES` keyed by topic.

Topic detection (simple keyword matching):
- `revenue | sales | growth` â revenue response
- `risk | risk factor | uncertainty` â risk response
- `margin | profitability | cost` â margin response
- anything else â default response

To add a new topic: add a key to `AI_RESPONSES` and add its trigger keywords to the `sendChat()` topic detection logic.

---

## v5 Upgrade Path (Real EDGAR Data)

When adding real data, use these SEC EDGAR APIs (no API key required, free):

```javascript
// 1. Look up CIK from ticker
const tickerMap = await fetch('https://www.sec.gov/files/company_tickers.json').then(r => r.json());
// Returns: { "0": { cik_str: 1045810, ticker: "NVDA", title: "NVIDIA CORP" }, ... }
const nvdaCik = '1045810'; // pad to 10 digits: '0001045810'

// 2. Fetch submission history (all filings)
const submissions = await fetch(`https://data.sec.gov/submissions/CIK0001045810.json`).then(r => r.json());
// Returns: { filings: { recent: { form: [...], date: [...], accessionNumber: [...] } } }

// 3. Fetch a specific filing document
// accessionNumber format: '0001045810-24-000029' â strip dashes â '0001045810240000029'
const docUrl = `https://www.sec.gov/Archives/edgar/data/1045810/000104581024000029/0001045810-24-000029-index.htm`;
```

CORS note: SEC EDGAR allows CORS from browsers. These fetches work directly from client-side JS with no proxy needed.

---

## VS Code Setup for This Project

### Recommended Extensions
- **Claude Code** (if using CLI) â run `claude` from the repo root
- **Prettier** â formatter, but disable for this file (it'll corrupt the encoding)
- **Live Server** â for local preview (note: encoding bugs only appear on htmlpreview, not local)
- **GitLens** â to track changes

### Claude Code Usage
When you run `claude` inside `edgar-disclosure-monitor/`, Claude Code reads this CLAUDE.md automatically and starts with full context. You can then say things like:
- "Add a 21st ticker for UBER with realistic mock data"
- "Fix the empty graph state bug (see bugs-and-fixes.md)"
- "Make the diff cards filter by materiality level"
- "Add a real EDGAR API call for NVDA's latest 10-K"

### Local Preview
Open `frontend/edgar_v2.html` directly in a browser with Live Server. All features work locally. The encoding bug only manifests on htmlpreview.github.io.

---

## Known Bugs (Open)

| ID | Bug | Fix |
|----|-----|-----|
| BUG-004 | D3 simulation keeps running after stock removed | Call `simulation.stop()` in `removeStock()` before rebuilding |
| BUG-005 | Chat textarea grows unbounded | Add `max-height: 120px; overflow-y: auto` to `#chat-input` |
| BUG-006 | Empty SVG visible when last stock removed | Check `pinnedStocks.length === 0` in `removeStock()`, show empty-state div |

---

## Git Workflow

```bash
# Standard workflow
git status
git diff frontend/edgar_v2.html
python3 fix_encoding.py          # ALWAYS run this before committing
git add frontend/edgar_v2.html
git commit -m "feat: describe what you changed

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
git push origin main
```

After pushing, wait ~30 seconds and hard refresh htmlpreview (Cmd+Shift+R) to see changes.

---

## Quick Reference

| Task | Command / Location |
|------|--------------------|
| Edit the app | `frontend/edgar_v2.html` |
| Fix encoding | `python3 fix_encoding.py` |
| View live | https://htmlpreview.github.io/?https://raw.githubusercontent.com/Krish-1717/edgar-disclosure-monitor/main/frontend/edgar_v2.html |
| Add a ticker | Add to `TICKER_DB`, `FILING_DATA`, and optionally `DIFFS` |
| Add an AI topic | Add key to `AI_RESPONSES`, add keyword to `sendChat()` |
| Change colors | Edit CSS variables at `:root` in `edgar_v2.html` |
| Roadmap | See `Second Brain/Projects/EDGAR-Monitor/roadmap.md` in Obsidian |
