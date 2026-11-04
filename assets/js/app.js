/*
 * app.js - EDGAR Disclosure Monitor demo app.
 * Hive network (D3 v7), crawler pipeline storytelling, analysis panel, AI workspace.
 * ALL DATA IS ILLUSTRATIVE. Pure ASCII: write non-ASCII as \uXXXX (see CLAUDE.md).
 */
(function () {
  'use strict';

  /* =====================================================================
   * DATA (existing mock model, preserved from frontend/edgar_v2.html)
   * ===================================================================== */
  var TICKER_DB = {
    'NVDA': {name:'NVIDIA Corporation', price:875.40, change:3.2, sector:'Technology', cik:'0001045810', exchange:'NASDAQ'},
    'AAPL': {name:'Apple Inc.', price:194.17, change:-0.8, sector:'Technology', cik:'0000320193', exchange:'NASDAQ'},
    'MSFT': {name:'Microsoft Corporation', price:415.52, change:1.3, sector:'Technology', cik:'0000789019', exchange:'NASDAQ'},
    'GOOGL': {name:'Alphabet Inc.', price:171.26, change:0.6, sector:'Communication', cik:'0001652044', exchange:'NASDAQ'},
    'META': {name:'Meta Platforms Inc.', price:502.33, change:-1.2, sector:'Communication', cik:'0001326801', exchange:'NASDAQ'},
    'AMZN': {name:'Amazon.com Inc.', price:184.72, change:2.1, sector:'Consumer', cik:'0001018724', exchange:'NASDAQ'},
    'TSLA': {name:'Tesla Inc.', price:177.90, change:-2.3, sector:'Consumer', cik:'0001318605', exchange:'NASDAQ'},
    'JPM': {name:'JPMorgan Chase & Co.', price:196.52, change:1.1, sector:'Financials', cik:'0000019617', exchange:'NYSE'},
    'BAC': {name:'Bank of America Corp.', price:38.74, change:0.4, sector:'Financials', cik:'0000070858', exchange:'NYSE'},
    'GS': {name:'Goldman Sachs Group', price:482.11, change:0.7, sector:'Financials', cik:'0000886982', exchange:'NYSE'},
    'NFLX': {name:'Netflix Inc.', price:638.47, change:2.6, sector:'Communication', cik:'0001065280', exchange:'NASDAQ'},
    'LLY': {name:'Eli Lilly and Company', price:741.20, change:1.8, sector:'Healthcare', cik:'0000059478', exchange:'NYSE'},
    'XOM': {name:'Exxon Mobil Corporation', price:118.56, change:0.3, sector:'Energy', cik:'0000034088', exchange:'NYSE'},
    'AMD': {name:'Advanced Micro Devices', price:154.33, change:1.9, sector:'Technology', cik:'0000002488', exchange:'NASDAQ'},
    'NKE': {name:'Nike Inc.', price:76.42, change:-0.9, sector:'Consumer', cik:'0000320187', exchange:'NYSE'},
    'BRKB': {name:'Berkshire Hathaway', price:371.25, change:0.5, sector:'Financials', cik:'0001067983', exchange:'NYSE'},
    'V': {name:'Visa Inc.', price:276.84, change:0.9, sector:'Financials', cik:'0001403161', exchange:'NYSE'},
    'MA': {name:'Mastercard Inc.', price:488.23, change:1.2, sector:'Financials', cik:'0001141391', exchange:'NYSE'},
    'UNH': {name:'UnitedHealth Group', price:528.17, change:-0.4, sector:'Healthcare', cik:'0000731766', exchange:'NYSE'},
    'PYPL': {name:'PayPal Holdings', price:68.94, change:-1.5, sector:'Financials', cik:'0001633917', exchange:'NASDAQ'}
  };

  var FILING_DATA = {
    'NVDA': [
      {id:'10-K 2024',form:'10-K',date:'Feb 21, 2024',current:true,materiality:0.78,burial:0.52,gap:0.64,group:'annual'},
      {id:'10-Q Q3\'24',form:'10-Q',date:'Nov 20, 2024',materiality:0.62,burial:0.38,gap:0.44,group:'quarterly'},
      {id:'10-Q Q2\'24',form:'10-Q',date:'Aug 28, 2024',materiality:0.55,burial:0.31,gap:0.40,group:'quarterly'},
      {id:'10-Q Q1\'24',form:'10-Q',date:'May 22, 2024',materiality:0.41,burial:0.28,gap:0.35,group:'quarterly'},
      {id:'10-K 2023',form:'10-K',date:'Feb 24, 2023',materiality:0.60,burial:0.44,gap:0.50,group:'annual'},
      {id:'8-K Nov\'24',form:'8-K',date:'Nov 7, 2024',materiality:0.33,burial:0.20,gap:0.28,group:'event'},
      {id:'8-K Sep\'24',form:'8-K',date:'Sep 11, 2024',materiality:0.28,burial:0.18,gap:0.22,group:'event'}
    ],
    'DEFAULT': [
      {id:'10-K 2024',form:'10-K',date:'Mar 15, 2024',current:true,materiality:0.52,burial:0.35,gap:0.44,group:'annual'},
      {id:'10-Q Q3\'24',form:'10-Q',date:'Oct 30, 2024',materiality:0.38,burial:0.24,gap:0.32,group:'quarterly'},
      {id:'10-Q Q2\'24',form:'10-Q',date:'Jul 31, 2024',materiality:0.31,burial:0.20,gap:0.26,group:'quarterly'},
      {id:'10-K 2023',form:'10-K',date:'Mar 10, 2023',materiality:0.44,burial:0.30,gap:0.38,group:'annual'},
      {id:'8-K Oct\'24',form:'8-K',date:'Oct 1, 2024',materiality:0.22,burial:0.14,gap:0.18,group:'event'}
    ]
  };

  var DIFFS = {
    'NVDA': [
      {type:'added',section:'Item 1A \u00b7 Risk Factors',text:'New risk factor: AI regulatory oversight and geopolitical export controls on H100/H200 chips to China mentioned for the first time.',before:null,after:'We are subject to U.S. export control laws, including the Export Administration Regulations (EAR). Recent export control rules restrict our ability to sell H100 and H200 products to customers in China and certain other countries...'},
      {type:'changed',section:'Item 7 \u00b7 MD&A',text:'Revenue guidance language materially strengthened from cautious to confident tone.',before:'"We expect revenues to remain consistent with prior periods, subject to market conditions and customer demand."',after:'"We anticipate significant revenue growth driven by accelerating AI infrastructure demand, with Data Center revenue expected to continue its strong trajectory."'},
      {type:'changed',section:'Item 7 \u00b7 MD&A',text:'Gross margin target raised from 66% to 73% in forward-looking statements.',before:'Our gross margin target remains in the mid-60% range as we scale production.',after:'We are targeting gross margins in the low-to-mid 70% range driven by product mix and operating leverage.'},
      {type:'removed',section:'Item 7 \u00b7 MD&A',text:'References to "uncertain demand environment" removed entirely from MD&A narrative.',before:'"Given the uncertain demand environment, we have taken a cautious approach to inventory management and capital deployment."',after:null},
      {type:'added',section:'Item 8 \u00b7 Financial Statements',text:'New segment disclosure: Data Center segment now separately reported with $18.4B quarterly revenue.',before:null,after:'Data Center revenue was $18.4 billion for the quarter ended January 28, 2024, representing a 409% year-over-year increase...'},
      {type:'changed',section:'Item 1 \u00b7 Business',text:'Company description expanded to emphasize AI platform positioning over traditional GPU narrative.',before:'NVIDIA is a visual computing company.',after:'NVIDIA is an AI computing company and the inventor of the GPU, which has emerged as the most powerful engine for AI and accelerated computing.'}
    ],
    'DEFAULT': [
      {type:'changed',section:'Item 7 \u00b7 MD&A',text:'Forward guidance language shifted from "expect" to "may" \u2014 increased hedging detected.',before:'"We expect continued growth in revenue and earnings per share through fiscal 2025."',after:'"Revenue and earnings per share may be affected by macroeconomic conditions, competitive pressures, and other factors outside our control."'},
      {type:'added',section:'Item 1A \u00b7 Risk Factors',text:'New risk factor added related to macroeconomic conditions and interest rate sensitivity.',before:null,after:'Rising interest rates and inflationary pressures may adversely affect consumer spending and demand for our products and services...'},
      {type:'changed',section:'Item 7 \u00b7 MD&A',text:'Capital expenditure guidance revised downward, citing prudent capital allocation.',before:'We plan to invest approximately $2.5B in capital expenditures in fiscal 2025.',after:'We expect capital expenditures to be in the range of $1.8B to $2.1B in fiscal 2025 as we prioritize return on invested capital.'}
    ]
  };

  var AI_RESPONSES = {
    revenue: function (t) { return 'Based on the most recent 10-K filing, ' + t + '\'s revenue grew significantly year-over-year. The MD&A section specifically highlights accelerating demand. The company raised its forward guidance language from "consistent" to "significant growth" \u2014 a material shift worth noting. I\'ve identified 3 specific passages where guidance language strengthened.'; },
    risk: function (t) { return 'The 10-K identifies several key risk factors. Most notable is a newly added section on regulatory and geopolitical risk \u2014 this language was not present in the prior 10-K, which is a material change. The filing also expanded discussion of competitive risk and supply chain dependencies. Want me to pull the exact passages?'; },
    margin: function (t) { return t + '\'s gross margin target was raised materially in this filing versus the prior period. The company revised its forward margin target from the mid-60% range to low-to-mid 70% \u2014 a 7-point increase. This change appeared in both the MD&A narrative and in the Business Outlook section. The prior filing used significantly more conservative language.'; },
    guidance: function (t) { return 'I found 4 instances where guidance language changed materially in ' + t + '\'s most recent filing. The most significant: "expect revenues to remain consistent" was replaced with "anticipate significant revenue growth" in Item 7. Additionally, the capex guidance range was tightened. These hedging-language shifts often precede earnings surprises.'; },
    insider: function (t, n) { return t + ' has ' + n + ' insider filings (Forms 4 and 144) in the demo set. Most are routine sales under pre-arranged 10b5-1 plans; one officer sale is larger than that officer\'s trailing 12-month average, which the forensic agent flags for context, not as a signal on its own.'; },
    diff: function (t, d) { return 'Versus the prior filing, ' + t + ' shows ' + d.length + ' material passage changes: ' + d.filter(function (x) { return x.type === 'added'; }).length + ' added, ' + d.filter(function (x) { return x.type === 'changed'; }).length + ' changed and ' + d.filter(function (x) { return x.type === 'removed'; }).length + ' removed. The headline: ' + d[0].text + ' Open the Changes tab to read each before/after pair.'; },
    default: function (t) { return 'Looking across ' + t + '\'s recent SEC filings, I can see several material changes. The most significant is a shift in hedging language in Item 7 and new disclosures in the risk factors section. Materiality score: 78/100 (HIGH). Want me to drill into specific sections \u2014 MD&A, Risk Factors, or Financial Statements?'; }
  };

  /* =====================================================================
   * FILING TAXONOMY
   * ===================================================================== */
  var CATEGORIES = {
    financial:   {label:'Financial reporting', color:'#a5adff', forms:['10-K','10-Q','8-K','20-F','6-K','11-K']},
    governance:  {label:'Governance & proxy',  color:'#5eead4', forms:['DEF 14A','PRE 14A','DEFA14A','DEF 14C','DEFM14A','DEFC14A']},
    insider:     {label:'Insider & ownership', color:'#e3c08a', forms:['Form 3','Form 4','Form 5','Form 144','SC 13D','SC 13G','13F-HR']},
    offerings:   {label:'Offerings',           color:'#c4a1ff', forms:['S-1','S-3','S-4','S-8','424B3','424B5','F-1','F-3']},
    ma:          {label:'M&A',                 color:'#ff9aae', forms:['SC TO-T','SC TO-I','SC 14D9','425','PREM14A']},
    debt:        {label:'Debt',                color:'#7dd3fc', forms:['424B2','FWP']},
    specialized: {label:'Specialized',         color:'#b6c0d4', forms:['SD','13F-NT','10-D','ABS-EE','NT 10-K','NT 10-Q','15-12B','15-12G']}
  };
  var CAT_ORDER = ['financial','governance','insider','offerings','ma','debt','specialized'];
  var TIER1 = {'10-K':1,'10-Q':1,'8-K':1,'DEF 14A':1,'Form 4':1,'S-1':1,'S-4':1};

  var ENTITY_TYPES = {
    holder: {label:'Shared shareholder', color:'#e3c08a'},
    exec:   {label:'Shared executive / director', color:'#5eead4'},
    deal:   {label:'Shared deal', color:'#ff9aae'}
  };
  // Illustrative relationships for the demo network. Not factual claims.
  var SHARED_ENTITIES = [
    {key:'vanguard', type:'holder', label:'Vanguard Group', note:'Passive holder reported on Schedule 13G', tickers:'*'},
    {key:'blackrock', type:'holder', label:'BlackRock', note:'Passive holder reported on Schedule 13G', tickers:'*'},
    {key:'berkshire', type:'holder', label:'Berkshire Hathaway', note:'Position reported on Form 13F-HR', tickers:['AAPL','BAC','V','MA','AMZN']},
    {key:'foundry', type:'deal', label:'Foundry supply agreements', note:'Shared supplier named in risk factors', tickers:['NVDA','AAPL','AMD']},
    {key:'aicloud', type:'deal', label:'AI compute capacity deals', note:'Customer and supplier relationships disclosed in 8-Ks', tickers:['NVDA','MSFT','GOOGL','AMZN','META']},
    {key:'cards', type:'deal', label:'Card network partnerships', note:'Commercial agreements', tickers:['V','MA','PYPL','JPM','BAC']},
    {key:'pharma', type:'deal', label:'Pharmacy benefit contracts', note:'Commercial relationships', tickers:['LLY','UNH']},
    {key:'streaming', type:'deal', label:'Cloud hosting agreement', note:'Vendor relationship', tickers:['NFLX','AMZN']},
    {key:'energy', type:'deal', label:'Materials offtake agreements', note:'Supply agreements', tickers:['TSLA','XOM']},
    {key:'board-tech', type:'exec', label:'Board interlock', note:'Director serving on several boards', tickers:['GOOGL','NFLX','META']},
    {key:'board-fin', type:'exec', label:'Board interlock', note:'Director serving on several boards', tickers:['JPM','GS','XOM']},
    {key:'exec-move', type:'exec', label:'Executive move', note:'Former officer now at a peer company', tickers:['TSLA','NKE','AAPL']}
  ];

  var CATEGORY_DIFFS = {
    governance: function (t) { return [
      {type:'changed',section:'Compensation Discussion & Analysis',text:'CEO pay ratio moved and a new performance metric was added to long-term incentives.',before:'Long-term incentive awards vest based on relative TSR.',after:'Long-term incentive awards vest based on relative TSR and a new free-cash-flow margin goal.'},
      {type:'added',section:'Proposal 4',text:'New shareholder proposal on AI governance and disclosure.',before:null,after:'Shareholders request a report on the oversight of artificial intelligence risks by the Board...'},
      {type:'removed',section:'Board Diversity Matrix',text:'One independent director did not stand for re-election.',before:'The Board consists of 12 directors, 11 of whom are independent.',after:null}
    ]; },
    insider: function (t) { return [
      {type:'added',section:'Table I \u00b7 Non-Derivative Securities',text:'Officer sale of common stock under a Rule 10b5-1 trading plan.',before:null,after:'Code S \u00b7 12,500 shares \u00b7 weighted average price disclosed in footnote (1).'},
      {type:'changed',section:'Beneficial ownership',text:'Direct holdings after the transaction fell versus the prior Form 4.',before:'Amount owned following reported transaction: 412,300 (D)',after:'Amount owned following reported transaction: 399,800 (D)'}
    ]; },
    offerings: function (t) { return [
      {type:'added',section:'Use of Proceeds',text:'Registration covers shares reserved for the employee equity plan.',before:null,after:'The shares registered hereby are issuable under the Company\'s Amended and Restated Equity Incentive Plan...'},
      {type:'changed',section:'Plan share reserve',text:'Share reserve increased versus the prior registration.',before:'Up to 25,000,000 shares',after:'Up to 40,000,000 shares'}
    ]; },
    ma: function (t) { return [
      {type:'added',section:'Background of the Transaction',text:'New disclosure of the deal timeline and board deliberations.',before:null,after:'On several occasions during the quarter, representatives of the parties discussed a potential business combination...'},
      {type:'changed',section:'Exchange ratio',text:'Consideration terms amended from the prior communication.',before:'0.42 shares per target share',after:'0.45 shares per target share plus cash in lieu of fractional shares'}
    ]; },
    debt: function (t) { return [
      {type:'added',section:'Pricing Supplement',text:'New structured note issuance under the shelf registration.',before:null,after:'Senior unsecured notes linked to an equity index, maturing in five years...'},
      {type:'changed',section:'Risk Factors',text:'Credit risk language expanded for the issuer.',before:'The notes are subject to our credit risk.',after:'The notes are subject to our credit risk, and actual or anticipated changes in our credit ratings may affect the market value of the notes.'}
    ]; },
    specialized: function (t) { return [
      {type:'changed',section:'Specialized disclosure',text:'Scope of the specialized report changed versus the prior year.',before:'Covers 214 suppliers in scope.',after:'Covers 238 suppliers in scope; 3 smelters newly identified.'}
    ]; }
  };

  /* =====================================================================
   * HELPERS
   * ===================================================================== */
  var reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  function $(id) { return document.getElementById(id); }
  function esc(s) { return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;'); }
  function hash(s) { var h = 2166136261; for (var i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619); } return h >>> 0; }
  function rng(seed) { return function () { seed |= 0; seed = seed + 0x6D2B79F5 | 0; var t = Math.imul(seed ^ seed >>> 15, 1 | seed); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }
  function store(key, val) { try { if (val === undefined) return JSON.parse(localStorage.getItem(key) || 'null'); localStorage.setItem(key, JSON.stringify(val)); } catch (e) { return null; } }
  function matColor(m) { return m >= 0.7 ? '#ff8f8f' : m >= 0.5 ? '#f6c177' : '#6ee7b7'; }
  function matClass(m) { return m >= 0.7 ? 'c-red' : m >= 0.5 ? 'c-amber' : 'c-green'; }
  function fmtKB(n) { return n > 1048576 ? (n / 1048576).toFixed(1) + ' MB' : Math.max(1, Math.round(n / 1024)) + ' KB'; }
  function edgarUrl(t, form) {
    var info = TICKER_DB[t];
    var type = form ? form.replace(/^Form /, '') : '';
    return 'https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=' + info.cik + '&type=' + encodeURIComponent(type) + '&dateb=&owner=include&count=40';
  }

  /* ---------- filing set per ticker: base FILING_DATA + seeded extras across categories ---------- */
  var filingCache = {};
  function getFilings(t) {
    if (filingCache[t]) return filingCache[t];
    var r = rng(hash(t));
    var info = TICKER_DB[t];
    var fin = info.sector === 'Financials';
    var list = (FILING_DATA[t] || FILING_DATA.DEFAULT).map(function (f) {
      var c = {}; for (var k in f) c[k] = f[k]; c.cat = 'financial'; return c;
    });
    var used = {};
    list.forEach(function (f) { used[f.id] = 1; });
    function add(form, cat, mat) {
      var m = Math.floor(r() * 11), day = 1 + Math.floor(r() * 27);
      var id = form + ' ' + MONTHS[m] + '\'24';
      var n = 2; while (used[id]) { id = form + ' ' + MONTHS[m] + '\'24 #' + n++; }
      used[id] = 1;
      list.push({ id: id, form: form, date: MONTHS[m] + ' ' + day + ', 2024', cat: cat, group: cat,
        materiality: +(mat != null ? mat : 0.12 + r() * 0.45).toFixed(2),
        burial: +(0.1 + r() * 0.45).toFixed(2), gap: +(0.1 + r() * 0.5).toFixed(2) });
    }
    add('DEF 14A', 'governance', 0.35 + r() * 0.3);
    if (r() < 0.55) add('DEFA14A', 'governance');
    if (r() < 0.12) add('PRE 14A', 'governance');
    var n4 = 2 + Math.floor(r() * 3);
    for (var i = 0; i < n4; i++) add('Form 4', 'insider', 0.15 + r() * 0.45);
    if (r() < 0.5) add('Form 144', 'insider');
    add('SC 13G', 'insider', 0.18 + r() * 0.2);
    if (r() < 0.15) add('SC 13D', 'insider', 0.5 + r() * 0.3);
    if (fin) add('13F-HR', 'insider');
    if (r() < 0.6) add('S-8', 'offerings');
    if (r() < 0.3) add('S-3', 'offerings');
    if (r() < 0.2) add('424B5', 'offerings');
    if (fin || r() < 0.3) { add('424B2', 'debt'); add('FWP', 'debt'); }
    if (r() < 0.2) { add('S-4', 'offerings', 0.6 + r() * 0.3); add('425', 'ma', 0.5 + r() * 0.3); }
    if (r() < 0.1) add('SC TO-I', 'ma');
    if ((info.sector === 'Technology' || info.sector === 'Consumer') && r() < 0.75) add('SD', 'specialized');
    if (t === 'JPM' || t === 'BAC') { add('10-D', 'specialized'); add('ABS-EE', 'specialized'); }
    if (r() < 0.35) add('11-K', 'financial');
    filingCache[t] = list;
    return list;
  }
  function diffsFor(f, t) {
    if (f.cat === 'financial') return DIFFS[t] || DIFFS.DEFAULT;
    return (CATEGORY_DIFFS[f.cat] || CATEGORY_DIFFS.specialized)(t);
  }
  function currentFiling(t) { var l = getFilings(t); for (var i = 0; i < l.length; i++) if (l[i].current) return l[i]; return l[0]; }

  /* =====================================================================
   * STATE
   * ===================================================================== */
  var pinned = [];          // tickers in watchlist order
  var reveal = {};          // ticker -> number of filings revealed in the graph
  var activeStock = null;
  var activeFiling = null;
  var mode = 'chat';
  var attachments = [];
  var WL_KEY = 'edm_watchlist_v1';

  /* =====================================================================
   * SIDEBAR: search + watchlist
   * ===================================================================== */
  var SEARCH_LIST = Object.keys(TICKER_DB).map(function (k) { return { ticker: k, name: TICKER_DB[k].name }; });
  var searchInput = $('ticker-search'), resultsEl = $('search-results'), combo = $('search-combo');
  var results = [], resIdx = -1;

  function renderResults() {
    if (!results.length) { closeResults(); return; }
    resultsEl.innerHTML = results.map(function (r, i) {
      var inList = pinned.indexOf(r.ticker) >= 0;
      return '<li role="option" id="opt-' + r.ticker + '" data-t="' + r.ticker + '" aria-selected="' + (i === resIdx) + '">' +
        '<span class="sr-t">' + r.ticker + '</span><span class="sr-n">' + esc(r.name) + '</span>' +
        (inList ? '<span class="sr-in">Added</span>' : '<span class="sr-a">+ Add</span>') + '</li>';
    }).join('');
    resultsEl.hidden = false;
    combo.setAttribute('aria-expanded', 'true');
    searchInput.setAttribute('aria-activedescendant', resIdx >= 0 ? 'opt-' + results[resIdx].ticker : '');
  }
  function closeResults() { resultsEl.hidden = true; combo.setAttribute('aria-expanded', 'false'); searchInput.removeAttribute('aria-activedescendant'); resIdx = -1; }
  searchInput.addEventListener('input', function () {
    var q = searchInput.value.trim().toUpperCase();
    if (!q) { results = []; closeResults(); return; }
    results = SEARCH_LIST.filter(function (s) { return s.ticker.indexOf(q) === 0 || s.name.toUpperCase().indexOf(q) >= 0; }).slice(0, 7);
    resIdx = results.length ? 0 : -1;
    renderResults();
  });
  searchInput.addEventListener('keydown', function (e) {
    if (e.key === 'ArrowDown' && results.length) { e.preventDefault(); resIdx = (resIdx + 1) % results.length; renderResults(); }
    else if (e.key === 'ArrowUp' && results.length) { e.preventDefault(); resIdx = (resIdx - 1 + results.length) % results.length; renderResults(); }
    else if (e.key === 'Enter') { e.preventDefault(); if (resIdx >= 0 && results[resIdx]) pick(results[resIdx].ticker); }
    else if (e.key === 'Escape') { closeResults(); }
  });
  resultsEl.addEventListener('mousedown', function (e) { e.preventDefault(); });
  resultsEl.addEventListener('click', function (e) { var li = e.target.closest('li[data-t]'); if (li) pick(li.getAttribute('data-t')); });
  searchInput.addEventListener('blur', function () { setTimeout(closeResults, 120); });
  function pick(t) { searchInput.value = ''; results = []; closeResults(); addStock(t); }

  function sparkline(t, change) {
    var r = rng(hash(t + 'spark')), pts = [], v = 50;
    for (var i = 0; i < 24; i++) { v += (r() - 0.5) * 7; v = Math.max(20, Math.min(80, v)); pts.push(v); }
    pts[pts.length - 1] = pts[pts.length - 2] + (change >= 0 ? 10 : -10);
    var W = 240, H = 30, mn = Math.min.apply(null, pts), mx = Math.max.apply(null, pts);
    var d = pts.map(function (p, i) { return (i ? 'L' : 'M') + (i / (pts.length - 1) * W).toFixed(1) + ',' + (H - (p - mn) / (mx - mn + 0.01) * H).toFixed(1); }).join(' ');
    var c = change >= 0 ? '#6ee7b7' : '#ff8f8f';
    return '<svg class="sc-sparkline" viewBox="0 0 ' + W + ' ' + H + '" preserveAspectRatio="none" aria-hidden="true"><path d="' + d + '" fill="none" stroke="' + c + '" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" vector-effect="non-scaling-stroke"/></svg>';
  }

  function renderSidebar() {
    var box = $('sidebar-stocks');
    $('sidebar-empty').hidden = pinned.length > 0;
    box.innerHTML = pinned.map(function (t) {
      var s = TICKER_DB[t], up = s.change >= 0, fl = getFilings(t);
      var days = 3 + (hash(t) % 25);
      return '<div class="stock-card' + (t === activeStock ? ' active' : '') + '" data-t="' + t + '">' +
        '<button type="button" class="sc-main" data-select="' + t + '" aria-pressed="' + (t === activeStock) + '" aria-label="Focus ' + esc(s.name) + '">' +
        '<div class="sc-top"><span class="sc-ticker">' + t + '</span><span class="sc-change ' + (up ? 'up' : 'dn') + '">' + (up ? '+' : '') + s.change.toFixed(1) + '%</span></div>' +
        '<div class="sc-name">' + esc(s.name) + '</div>' +
        '<div class="sc-mid"><span class="sc-price">$' + s.price.toFixed(2) + '</span><span><span class="sc-badge">' + fl.length + ' filings</span><span class="sc-badge">' + days + 'd ago</span></span></div>' +
        sparkline(t, s.change) + '</button>' +
        '<button type="button" class="sc-remove" data-remove="' + t + '" aria-label="Remove ' + t + ' from watchlist">' +
        '<svg viewBox="0 0 24 24" width="14" height="14" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg></button></div>';
    }).join('');
  }
  $('sidebar-stocks').addEventListener('click', function (e) {
    var rm = e.target.closest('[data-remove]');
    if (rm) { removeStock(rm.getAttribute('data-remove')); return; }
    var sel = e.target.closest('[data-select]');
    if (sel) { selectStock(sel.getAttribute('data-select')); closeSidebarMobile(); }
  });
  $('quick-add').innerHTML = ['NVDA', 'MSFT', 'AAPL', 'JPM', 'LLY'].map(function (t) { return '<button type="button" data-quick="' + t + '">' + t + '</button>'; }).join('');
  $('quick-add').addEventListener('click', function (e) { var b = e.target.closest('[data-quick]'); if (b) addStock(b.getAttribute('data-quick')); });

  /* mobile drawer */
  var sbToggle = $('sidebar-toggle'), sidebar = $('sidebar');
  sbToggle.addEventListener('click', function () {
    var open = !sidebar.classList.contains('open');
    sidebar.classList.toggle('open', open);
    sbToggle.setAttribute('aria-expanded', String(open));
    if (open) searchInput.focus();
  });
  function closeSidebarMobile() { if (sidebar.classList.contains('open')) { sidebar.classList.remove('open'); sbToggle.setAttribute('aria-expanded', 'false'); } }

  /* =====================================================================
   * WATCHLIST ACTIONS
   * ===================================================================== */
  function save() { store(WL_KEY, pinned); }

  function addStock(t, opts) {
    t = String(t || '').toUpperCase();
    if (!TICKER_DB[t]) return false;
    opts = opts || {};
    if (pinned.indexOf(t) >= 0) { selectStock(t); return true; }
    pinned.push(t);
    reveal[t] = (opts.instant || reduceMotion) ? getFilings(t).length : 0;
    save();
    renderSidebar();
    selectStock(t, { keepPanel: false });
    updateGraph();
    if (!opts.instant) runPipeline(t); else setIdleStatus();
    return true;
  }

  function removeStock(t) {
    var i = pinned.indexOf(t);
    if (i < 0) return;
    pinned.splice(i, 1);
    delete reveal[t];
    save();
    if (activeFiling && activeFiling.ticker === t) closePanel();
    if (activeStock === t) activeStock = pinned.length ? pinned[pinned.length - 1] : null;
    renderSidebar();
    updateTopbar();
    updateGraph();
    setIdleStatus();
  }

  function selectStock(t) {
    activeStock = t;
    renderSidebar();
    updateTopbar();
    highlightCluster(t);
    $('ws-context').textContent = 'Workspace \u00b7 ' + t;
    $('chat-input').placeholder = 'Ask about ' + t + ' filings, or type "add MSFT"';
  }

  function updateTopbar() {
    var ctx = $('tb-context'), link = $('tb-edgar-link');
    if (!activeStock) {
      ctx.innerHTML = '<span class="tb-hint">Add a ticker to grow the hive</span>';
      link.href = 'https://www.sec.gov/edgar/search/';
      return;
    }
    var s = TICKER_DB[activeStock];
    ctx.innerHTML = '<b>' + activeStock + '</b><span class="sep">\u00b7</span><span class="co">' + esc(s.name) + '</span><span class="sep">\u00b7</span><span class="co">' + esc(s.sector) + '</span><span class="sep">\u00b7</span><span>' + getFilings(activeStock).length + ' filings</span>';
    link.href = edgarUrl(activeStock, '10-K');
  }

  /* =====================================================================
   * CRAWLER PIPELINE STRIP (presentation only)
   * ===================================================================== */
  var pipeToken = 0;
  var stageEls = Array.prototype.slice.call(document.querySelectorAll('#pipeline li'));
  function setIdleStatus() {
    stageEls.forEach(function (el) { el.classList.remove('active'); });
    var n = pinned.reduce(function (a, t) { return a + getFilings(t).length; }, 0);
    $('pipeline-status').textContent = pinned.length ? 'Watching ' + pinned.length + ' compan' + (pinned.length === 1 ? 'y' : 'ies') + ' \u00b7 ' + n + ' filings indexed' : 'Idle \u00b7 waiting for a watchlist';
  }
  function runPipeline(t) {
    var token = ++pipeToken;
    var fl = getFilings(t);
    var total = fl.length;
    var mb = (fl.length * 0.31 + (hash(t) % 9) / 10).toFixed(1);
    var steps = [
      { s: 0, text: t + ' \u00b7 discovering accession numbers\u2026', reveal: Math.ceil(total * 0.45) },
      { s: 1, text: t + ' \u00b7 retrieving ' + total + ' documents (' + mb + ' MB)', reveal: total },
      { s: 2, text: t + ' \u00b7 parsing HTML \u00b7 iXBRL \u00b7 PDF' },
      { s: 3, text: t + ' \u00b7 4 agents analyzing (financial, risk, diff, forensic)' },
      { s: 4, text: t + ' \u00b7 cited report ready \u00b7 ' + (DIFFS[t] || DIFFS.DEFAULT).length + ' material changes' }
    ];
    stageEls.forEach(function (el) { el.classList.remove('active', 'done'); });
    var i = 0;
    function next() {
      if (token !== pipeToken) return;
      if (i > 0) { stageEls[steps[i - 1].s].classList.remove('active'); stageEls[steps[i - 1].s].classList.add('done'); }
      if (i >= steps.length) { setTimeout(function () { if (token === pipeToken) { stageEls.forEach(function (el) { el.classList.remove('done'); }); setIdleStatus(); } }, 2600); return; }
      var st = steps[i];
      stageEls[st.s].classList.add('active');
      $('pipeline-status').textContent = st.text;
      if (st.reveal) growTo(t, st.reveal, 760);
      i++;
      setTimeout(next, 900);
    }
    next();
  }
  function growTo(t, n, dur) {
    var start = reveal[t] || 0;
    if (n <= start) return;
    var count = n - start, step = Math.max(40, dur / count), k = 0;
    var iv = setInterval(function () {
      if (pinned.indexOf(t) < 0) { clearInterval(iv); return; }
      reveal[t] = Math.min(n, start + (++k));
      updateGraph();
      if (reveal[t] >= n) clearInterval(iv);
    }, step);
  }

  /* =====================================================================
   * HIVE NETWORK (D3 v7)
   * ===================================================================== */
  var hasD3 = typeof window.d3 !== 'undefined';
  var svg, root, gLinks, gShared, gPulses, gNodes, zoom, sim, nodeMap = {}, gNodesData = [], gLinksData = [], sharedLinks = [], W = 800, H = 600;
  var tooltip = $('tooltip'), area = $('graph-area');

  function nodeR(d) {
    if (d.kind === 'hub') return 22;
    if (d.kind === 'cat') return 4;
    if (d.kind === 'entity') return 8;
    return d.tier1 ? 8 : 5;
  }

  function initGraph() {
    if (!hasD3) {
      $('graph-empty').querySelector('h1').textContent = 'Network view unavailable.';
      $('graph-empty').querySelector('p').textContent = 'The D3 library could not load (offline or blocked). The watchlist, analysis panel and workspace still work.';
      return;
    }
    svg = d3.select('#hive');
    var defs = svg.append('defs');
    defs.append('filter').attr('id', 'soft-glow').attr('x', '-100%').attr('y', '-100%').attr('width', '300%').attr('height', '300%')
      .html('<feGaussianBlur stdDeviation="3" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>');
    var rg = defs.append('radialGradient').attr('id', 'hub-halo');
    rg.append('stop').attr('offset', '0').attr('stop-color', '#7c86ff').attr('stop-opacity', 0.45);
    rg.append('stop').attr('offset', '1').attr('stop-color', '#7c86ff').attr('stop-opacity', 0);
    root = svg.append('g');
    gLinks = root.append('g');
    gShared = root.append('g');
    gPulses = root.append('g');
    gNodes = root.append('g');
    zoom = d3.zoom().scaleExtent([0.2, 3]).on('zoom', function (e) { root.attr('transform', e.transform); });
    svg.call(zoom).on('dblclick.zoom', null);
    measure();
    svg.call(zoom.transform, d3.zoomIdentity.translate(W / 2, H / 2));
    sim = d3.forceSimulation()
      .force('link', d3.forceLink().id(function (d) { return d.id; })
        .distance(function (l) { return l.kind === 'hc' ? 52 : l.kind === 'cf' ? 22 : 150; })
        .strength(function (l) { return l.kind === 'shared' ? 0.04 : 0.9; }))
      .force('charge', d3.forceManyBody().strength(function (d) { return d.kind === 'hub' ? -420 : d.kind === 'entity' ? -140 : d.kind === 'cat' ? -70 : -26; }).distanceMax(520))
      .force('collide', d3.forceCollide().radius(function (d) { return nodeR(d) + (d.kind === 'hub' ? 10 : 2.5); }))
      .force('x', d3.forceX(function (d) { return d.tx || 0; }).strength(function (d) { return d.kind === 'hub' ? 0.09 : d.kind === 'entity' ? 0.03 : 0.012; }))
      .force('y', d3.forceY(function (d) { return d.ty || 0; }).strength(function (d) { return d.kind === 'hub' ? 0.09 : d.kind === 'entity' ? 0.03 : 0.012; }))
      .alphaDecay(0.028)
      .on('tick', ticked);
    if (window.ResizeObserver) new ResizeObserver(function () { measure(); }).observe(area);
    if (!reduceMotion) setInterval(pulse, 1100);
    renderLegend();
  }
  function measure() { W = area.clientWidth || 800; H = area.clientHeight || 600; }

  function hubTarget(i) {
    if (i === 0) return { x: 0, y: 0 };
    var a = i * 2.39996, r = 200 * Math.sqrt(i);
    return { x: Math.cos(a) * r, y: Math.sin(a) * r * 0.82 };
  }

  function buildData() {
    var nodes = [], links = [], keep = {};
    function node(id, props, near) {
      var n = nodeMap[id];
      if (!n) {
        n = { id: id };
        var j = function () { return (Math.random() - 0.5) * 20; };
        n.x = (near ? near.x : 0) + j(); n.y = (near ? near.y : 0) + j();
        n.isNew = true;
        nodeMap[id] = n;
      }
      for (var k in props) n[k] = props[k];
      keep[id] = 1;
      nodes.push(n);
      return n;
    }
    pinned.forEach(function (t, i) {
      var tg = hubTarget(i);
      var hub = node('hub:' + t, { kind: 'hub', ticker: t, tx: tg.x, ty: tg.y, label: t }, nodeMap['hub:' + t] ? null : tg);
      var fl = getFilings(t).slice(0, reveal[t] || 0);
      var cats = {};
      fl.forEach(function (f, k) {
        if (!cats[f.cat]) {
          var ci = CAT_ORDER.indexOf(f.cat), a = ci / CAT_ORDER.length * Math.PI * 2;
          cats[f.cat] = node('cat:' + t + ':' + f.cat, { kind: 'cat', ticker: t, cat: f.cat, tx: tg.x + Math.cos(a) * 60, ty: tg.y + Math.sin(a) * 60 }, hub);
          links.push({ id: 'hc:' + t + ':' + f.cat, source: hub.id, target: cats[f.cat].id, kind: 'hc', cat: f.cat });
        }
        var fn = node('f:' + t + ':' + f.id, { kind: 'filing', ticker: t, cat: f.cat, filing: f, tier1: !!TIER1[f.form], tx: cats[f.cat].tx, ty: cats[f.cat].ty }, cats[f.cat]);
        links.push({ id: 'cf:' + t + ':' + f.id, source: cats[f.cat].id, target: fn.id, kind: 'cf', cat: f.cat });
      });
    });
    sharedLinks = [];
    SHARED_ENTITIES.forEach(function (e) {
      var ts = (e.tickers === '*' ? pinned : e.tickers.filter(function (t) { return pinned.indexOf(t) >= 0; }));
      if (ts.length < 2) return;
      var sx = 0, sy = 0;
      ts.forEach(function (t) { var h = nodeMap['hub:' + t]; sx += h.tx; sy += h.ty; });
      var near = nodeMap['hub:' + ts[0]];
      var en = node('e:' + e.key, { kind: 'entity', etype: e.type, label: e.label, note: e.note, tickers: ts, tx: sx / ts.length + (hash(e.key) % 60 - 30), ty: sy / ts.length + (hash(e.key + 'y') % 60 - 30) }, near);
      ts.forEach(function (t) {
        var l = { id: 'sh:' + e.key + ':' + t, source: en.id, target: 'hub:' + t, kind: 'shared', etype: e.type };
        links.push(l); sharedLinks.push(l);
      });
    });
    Object.keys(nodeMap).forEach(function (id) { if (!keep[id]) delete nodeMap[id]; });
    gNodesData = nodes; gLinksData = links;
  }

  function updateGraph() {
    $('graph-empty').hidden = pinned.length > 0;
    if (!hasD3) return;
    buildData();
    var normal = gLinksData.filter(function (l) { return l.kind !== 'shared'; });
    var shared = gLinksData.filter(function (l) { return l.kind === 'shared'; });

    gLinks.selectAll('line').data(normal, function (d) { return d.id; }).join(
      function (en) { return en.append('line').attr('stroke', function (d) { return d.kind === 'hc' ? 'rgba(165,173,255,0.35)' : CATEGORIES[d.cat].color; })
        .attr('stroke-width', function (d) { return d.kind === 'hc' ? 1.2 : 0.8; }).attr('opacity', 0)
        .call(function (s) { s.transition().duration(reduceMotion ? 0 : 900).attr('opacity', function (d) { return d.kind === 'hc' ? 1 : 0.32; }); }); },
      function (up) { return up; },
      function (ex) { return ex.remove(); });

    gShared.selectAll('line').data(shared, function (d) { return d.id; }).join(
      function (en) { return en.append('line').attr('class', 'shared').attr('stroke', function (d) { return ENTITY_TYPES[d.etype].color; })
        .attr('stroke-width', 1.1).attr('stroke-dasharray', '2 6').attr('stroke-linecap', 'round'); },
      function (up) { return up; },
      function (ex) { return ex.remove(); });

    var sel = gNodes.selectAll('g.node').data(gNodesData, function (d) { return d.id; });
    sel.exit().remove();
    var en = sel.enter().append('g').attr('class', function (d) { return 'node n-' + d.kind; });
    var inner = en.append('g').attr('class', 'inner');
    en.each(function (d) {
      var g = d3.select(this).select('.inner');
      if (d.kind === 'hub') {
        g.append('circle').attr('class', 'halo').attr('r', 46).attr('fill', 'url(#hub-halo)');
        g.append('circle').attr('r', 22).attr('fill', '#0b0e1f').attr('stroke', '#c9ceff').attr('stroke-width', 1.6).attr('filter', 'url(#soft-glow)');
        g.append('text').text(d.label).attr('text-anchor', 'middle').attr('dy', '0.35em').attr('font-size', d.label.length > 4 ? 10 : 11).attr('font-weight', 600).attr('fill', '#eef1f8').attr('font-family', 'IBM Plex Mono, monospace');
        g.append('circle').attr('class', 'focus-ring').attr('r', 27);
      } else if (d.kind === 'cat') {
        g.append('circle').attr('r', 4).attr('fill', CATEGORIES[d.cat].color).attr('opacity', 0.9);
      } else if (d.kind === 'entity') {
        g.append('path').attr('d', 'M0,-8L8,0L0,8L-8,0Z').attr('fill', ENTITY_TYPES[d.etype].color).attr('fill-opacity', 0.85).attr('filter', 'url(#soft-glow)');
        g.append('circle').attr('class', 'focus-ring').attr('r', 12);
      } else {
        var c = CATEGORIES[d.cat].color;
        if (d.tier1) g.append('circle').attr('r', 11.5).attr('fill', 'none').attr('stroke', '#eef1f8').attr('stroke-opacity', 0.75).attr('stroke-width', 1.1).attr('filter', 'url(#soft-glow)');
        g.append('circle').attr('class', 'core').attr('r', nodeR(d)).attr('fill', c).attr('fill-opacity', d.tier1 ? 0.95 : 0.7);
        if (d.tier1) g.append('text').text(d.filing.form.replace('Form ', 'F')).attr('text-anchor', 'middle').attr('dy', 22).attr('font-size', 8.5).attr('fill', '#949db2');
        g.append('circle').attr('class', 'focus-ring').attr('r', d.tier1 ? 15 : 9);
      }
    });
    en.filter(function (d) { return d.kind !== 'cat'; })
      .attr('tabindex', 0).attr('role', 'button')
      .attr('aria-label', function (d) { return ariaFor(d); })
      .on('click', function (ev, d) { if (ev.defaultPrevented) return; activate(d); })
      .on('keydown', function (ev, d) { if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); activate(d); } })
      .on('mouseenter focus', function (ev, d) { showTip(ev, d); })
      .on('mousemove', function (ev) { moveTip(ev); })
      .on('mouseleave blur', hideTip)
      .call(d3.drag()
        .on('start', function (ev, d) { if (!ev.active) sim.alphaTarget(0.25).restart(); d.fx = d.x; d.fy = d.y; })
        .on('drag', function (ev, d) { d.fx = ev.x; d.fy = ev.y; })
        .on('end', function (ev, d) { if (!ev.active) sim.alphaTarget(0); d.fx = null; d.fy = null; }));
    if (!reduceMotion) {
      inner.attr('transform', 'scale(0.01)').transition().duration(700).ease(d3.easeCubicOut).attr('transform', 'scale(1)');
    }
    gNodesData.forEach(function (n) { n.isNew = false; });

    sim.nodes(gNodesData);
    sim.force('link').links(gLinksData);
    sim.alpha(reduceMotion ? 0.9 : 0.6).restart();
    if (reduceMotion) { for (var i = 0; i < 160; i++) sim.tick(); ticked(); }
    clearTimeout(updateGraph.fitT);
    updateGraph.fitT = setTimeout(fit, reduceMotion ? 0 : 900);
    if (activeStock) highlightCluster(activeStock);
  }

  function ticked() {
    gLinks.selectAll('line').attr('x1', function (d) { return d.source.x; }).attr('y1', function (d) { return d.source.y; }).attr('x2', function (d) { return d.target.x; }).attr('y2', function (d) { return d.target.y; });
    gShared.selectAll('line').attr('x1', function (d) { return d.source.x; }).attr('y1', function (d) { return d.source.y; }).attr('x2', function (d) { return d.target.x; }).attr('y2', function (d) { return d.target.y; });
    gNodes.selectAll('g.node').attr('transform', function (d) { return 'translate(' + d.x.toFixed(1) + ',' + d.y.toFixed(1) + ')'; });
  }

  function fit() {
    if (!hasD3 || !gNodesData.length) return;
    measure();
    var x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
    gNodesData.forEach(function (n) { x0 = Math.min(x0, n.x); y0 = Math.min(y0, n.y); x1 = Math.max(x1, n.x); y1 = Math.max(y1, n.y); });
    var pad = 70, bw = Math.max(1, x1 - x0) + pad * 2, bh = Math.max(1, y1 - y0) + pad * 2;
    var k = Math.min(1.5, W / bw, H / bh);
    var tx = W / 2 - k * (x0 + x1) / 2, ty = H / 2 - k * (y0 + y1) / 2;
    svg.transition().duration(reduceMotion ? 0 : 1100).ease(d3.easeCubicInOut).call(zoom.transform, d3.zoomIdentity.translate(tx, ty).scale(k));
  }

  function pulse() {
    if (document.hidden || !sharedLinks.length) return;
    var l = sharedLinks[Math.floor(Math.random() * sharedLinks.length)];
    if (!l.source || typeof l.source !== 'object') return;
    var flip = Math.random() < 0.5, a = flip ? l.target : l.source, b = flip ? l.source : l.target;
    gPulses.append('circle').attr('r', 2.6).attr('fill', ENTITY_TYPES[l.etype].color).attr('filter', 'url(#soft-glow)').attr('opacity', 0.95)
      .transition().duration(1700).ease(d3.easeCubicInOut)
      .attrTween('transform', function () { return function (t) { return 'translate(' + (a.x + (b.x - a.x) * t) + ',' + (a.y + (b.y - a.y) * t) + ')'; }; })
      .attr('opacity', 0.2).remove();
  }

  function highlightCluster(t) {
    if (!hasD3 || !gNodes) return;
    gNodes.selectAll('g.n-hub').select('circle:nth-child(2)').attr('stroke-width', function (d) { return d.ticker === t ? 2.6 : 1.6; }).attr('stroke', function (d) { return d.ticker === t ? '#eef0ff' : '#c9ceff'; });
  }

  function ariaFor(d) {
    if (d.kind === 'hub') return d.ticker + ', ' + TICKER_DB[d.ticker].name + ' cluster. Press Enter to focus.';
    if (d.kind === 'entity') return ENTITY_TYPES[d.etype].label + ': ' + d.label + ', links ' + d.tickers.join(', ');
    return d.ticker + ' ' + d.filing.id + ', ' + CATEGORIES[d.cat].label + ', filed ' + d.filing.date + ', materiality ' + Math.round(d.filing.materiality * 100) + '. Press Enter to analyze.';
  }
  function activate(d) {
    if (d.kind === 'hub') { selectStock(d.ticker); return; }
    if (d.kind === 'entity') { explainEntity(d); return; }
    if (d.kind === 'filing') { if (activeStock !== d.ticker) selectStock(d.ticker); openPanel(d.filing, d.ticker); }
  }
  function showTip(ev, d) {
    var html;
    if (d.kind === 'hub') { var s = TICKER_DB[d.ticker]; html = '<b>' + d.ticker + '</b> \u00b7 ' + esc(s.name) + '<br>' + getFilings(d.ticker).length + ' filings \u00b7 ' + esc(s.sector); }
    else if (d.kind === 'entity') html = '<b>' + esc(d.label) + '</b><br>' + esc(ENTITY_TYPES[d.etype].label) + ' \u00b7 ' + d.tickers.join(', ') + '<br><span style="color:#949db2">' + esc(d.note) + ' (illustrative)</span>';
    else html = '<b>' + esc(d.filing.id) + '</b>' + (d.tier1 ? ' \u00b7 Tier 1' : '') + '<br>' + esc(CATEGORIES[d.cat].label) + '<br>Filed ' + esc(d.filing.date) + ' \u00b7 Materiality ' + Math.round(d.filing.materiality * 100);
    tooltip.innerHTML = html;
    tooltip.classList.add('visible');
    if (ev.type === 'focus') {
      var r = ev.target.getBoundingClientRect(), ar = area.getBoundingClientRect();
      tooltip.style.left = Math.min(ar.width - 250, r.right - ar.left + 8) + 'px';
      tooltip.style.top = (r.top - ar.top - 8) + 'px';
    } else moveTip(ev);
  }
  function moveTip(ev) {
    var ar = area.getBoundingClientRect();
    tooltip.style.left = Math.min(ar.width - 250, ev.clientX - ar.left + 14) + 'px';
    tooltip.style.top = (ev.clientY - ar.top - 10) + 'px';
  }
  function hideTip() { tooltip.classList.remove('visible'); }

  function renderLegend() {
    var lg = $('legend');
    lg.innerHTML = '<h2>Filing categories</h2><ul>' + CAT_ORDER.map(function (c) {
      return '<li><i style="background:' + CATEGORIES[c].color + '"></i>' + esc(CATEGORIES[c].label) + '</li>';
    }).join('') + '<li class="tier"><i></i>Tier 1 form (10-K, 10-Q, 8-K, DEF 14A, Form 4, S-1, S-4)</li></ul>' +
      '<h2>Shared links</h2><ul>' + Object.keys(ENTITY_TYPES).map(function (k) {
        return '<li class="shared-k"><i style="background:' + ENTITY_TYPES[k].color + '"></i>' + esc(ENTITY_TYPES[k].label) + '</li>';
      }).join('') + '</ul><p>Relationships are illustrative demo data.</p>';
    if (window.innerWidth < 700) toggleLegend(false);
  }
  function toggleLegend(show) {
    var lg = $('legend'), b = $('legend-btn');
    if (show === undefined) show = lg.hidden;
    lg.hidden = !show;
    b.setAttribute('aria-expanded', String(show));
  }
  $('legend-btn').addEventListener('click', function () { toggleLegend(); });
  $('fit-btn').addEventListener('click', fit);
  $('load-demo').addEventListener('click', loadDemo);
  function loadDemo() {
    var demo = ['NVDA', 'MSFT', 'AMZN', 'GOOGL', 'META'];
    demo.forEach(function (t, i) {
      setTimeout(function () { addStock(t, { instant: reduceMotion }); }, reduceMotion ? 0 : i * 1500);
    });
  }

  /* =====================================================================
   * ANALYSIS PANEL
   * ===================================================================== */
  var panel = $('panel'), panelBody = $('panel-body'), tabs = Array.prototype.slice.call(document.querySelectorAll('.tabs [role="tab"]'));
  var panelToken = 0, lastFocus = null, diffFilter = 'all';

  function openPanel(f, t) {
    activeFiling = { filing: f, ticker: t };
    lastFocus = document.activeElement;
    $('panel-kicker').textContent = t + ' \u00b7 ' + CATEGORIES[f.cat].label.toUpperCase();
    $('panel-title').textContent = f.id;
    $('panel-sub').textContent = f.form + ' \u00b7 Filed ' + f.date + (TIER1[f.form] ? ' \u00b7 Tier 1' : '');
    panel.classList.add('open');
    panel.setAttribute('aria-hidden', 'false');
    $('ws-context').textContent = 'Workspace \u00b7 ' + t + ' \u00b7 ' + f.id;
    diffFilter = 'all';
    setTab('crawler');
    setTimeout(function () { $('panel-close').focus(); }, 50);
  }
  function closePanel() {
    panelToken++;
    panel.classList.remove('open');
    panel.setAttribute('aria-hidden', 'true');
    activeFiling = null;
    if (activeStock) $('ws-context').textContent = 'Workspace \u00b7 ' + activeStock;
    if (lastFocus && document.body.contains(lastFocus)) { try { lastFocus.focus(); } catch (e) {} }
  }
  $('panel-close').addEventListener('click', closePanel);
  document.addEventListener('keydown', function (e) {
    if (e.key !== 'Escape') return;
    if (document.querySelector('dialog[open]')) return;
    if (panel.classList.contains('open')) closePanel();
    else closeSidebarMobile();
  });

  function setTab(name) {
    tabs.forEach(function (b) { var on = b.getAttribute('data-tab') === name; b.setAttribute('aria-selected', String(on)); b.tabIndex = on ? 0 : -1; });
    panelBody.setAttribute('aria-labelledby', 'tab-' + name);
    if (!activeFiling) return;
    var f = activeFiling.filing, t = activeFiling.ticker;
    panelToken++;
    if (name === 'crawler') renderCrawler(f, t);
    else if (name === 'diff') renderDiff(f, t);
    else renderScore(f, t);
  }
  tabs.forEach(function (b, i) {
    b.addEventListener('click', function () { setTab(b.getAttribute('data-tab')); });
    b.addEventListener('keydown', function (e) {
      var j = e.key === 'ArrowRight' ? (i + 1) % tabs.length : e.key === 'ArrowLeft' ? (i - 1 + tabs.length) % tabs.length : -1;
      if (j >= 0) { e.preventDefault(); tabs[j].focus(); setTab(tabs[j].getAttribute('data-tab')); }
    });
  });

  function crawlStages(f, t) {
    var info = TICKER_DB[t], r = rng(hash(t + f.id)), xml = f.cat === 'insider';
    var acc = info.cik.slice(-7) + '-24-' + String(100000 + Math.floor(r() * 899999));
    var kb = Math.round(300 + r() * 700);
    var diffs = diffsFor(f, t);
    return [
      { key: 'discover', label: 'Discover', lines: [
        ['l-info', '> Resolving CIK via submissions API\u2026'],
        ['l-ok', '> CIK ' + info.cik + ' \u00b7 ' + info.name],
        ['l-ok', '> New accession ' + acc + ' (' + f.form + ')']] },
      { key: 'retrieve', label: 'Retrieve', lines: [
        ['l-info', '> GET primary document: ' + kb + ' KB ' + (xml ? 'XML' : 'HTML')],
        ['l-info', '> GET ' + (xml ? 1 : 6 + Math.floor(r() * 10)) + ' exhibits \u00b7 rate limit 10 req/s respected']] },
      { key: 'parse', label: 'Parse', chips: xml ? ['XML'] : ['HTML', 'iXBRL', 'PDF'], lines: xml ? [
        ['l-ok', '> XML: ownership document \u00b7 ' + (1 + Math.floor(r() * 4)) + ' transactions']] : [
        ['l-ok', '> HTML: ' + (8 + Math.floor(r() * 12)) + ' sections segmented (Items 1, 1A, 7, 8\u2026)'],
        ['l-ok', '> iXBRL: ' + (600 + Math.floor(r() * 1400)) + ' tagged facts (us-gaap, dei)'],
        ['l-mut', '  PDF: ' + Math.floor(r() * 3) + ' exhibits with text layer']] },
      { key: 'agents', label: 'AI agents', chips: ['Financial', 'Risk', 'Historical diff', 'Forensic'], lines: [
        ['l-info', '> Financial agent: key metrics reconciled to XBRL facts'],
        ['l-info', '> Risk agent: ' + diffs.filter(function (d) { return d.type === 'added'; }).length + ' new disclosures flagged'],
        ['l-info', '> Historical diff agent: ' + diffs.length + ' material passages vs prior filing'],
        [f.burial > 0.45 ? 'l-warn' : 'l-mut', '> Forensic agent: burial score ' + Math.round(f.burial * 100) + (f.burial > 0.45 ? ' \u00b7 key detail sits in footnotes' : ' \u00b7 no anomalies')]] },
      { key: 'report', label: 'Cited report', lines: [
        ['l-warn', '> Materiality ' + Math.round(f.materiality * 100) + '/100 \u00b7 ' + (f.materiality >= 0.7 ? 'HIGH' : f.materiality >= 0.5 ? 'MEDIUM' : 'LOW')],
        ['l-ok', '> \u2713 Cited report ready']] }
    ];
  }

  function renderCrawler(f, t) {
    var token = panelToken;
    var stages = crawlStages(f, t);
    var diffs = diffsFor(f, t);
    var secs = (1.4 + (hash(f.id + t) % 30) / 10).toFixed(1);
    panelBody.innerHTML =
      '<ol class="stages">' + stages.map(function (s, i) {
        return '<li class="stage" data-i="' + i + '"><div class="stage-h"><span>' + esc(s.label) + '</span><span class="st">queued</span></div>' +
          (s.chips ? '<div class="chips">' + s.chips.map(function (c) { return '<span class="chip">' + esc(c) + '</span>'; }).join('') + '</div>' : '') + '</li>';
      }).join('') + '</ol>' +
      '<div class="log" id="crawl-log" role="log" aria-label="Crawler log"></div>' +
      '<div class="report-card" id="report-card"><h3>Cited summary</h3><p>' + esc(diffs[0].text) + '</p>' +
      '<div class="cites">' + diffs.slice(0, 3).map(function (d, i) { return '<button type="button" class="cite" data-goto="diff">[' + (i + 1) + '] ' + esc(d.section) + '</button>'; }).join('') + '</div>' +
      '<div class="stats"><div class="stat"><b class="' + matClass(f.materiality) + '">' + Math.round(f.materiality * 100) + '</b><span>Materiality</span></div>' +
      '<div class="stat"><b class="c-amber">' + diffs.length + '</b><span>Changes</span></div>' +
      '<div class="stat"><b class="c-accent">' + secs + 's</b><span>Crawl time</span></div></div></div>' +
      '<p class="panel-foot"><a href="' + edgarUrl(t, f.form) + '" target="_blank" rel="noopener">View ' + esc(t) + ' ' + esc(f.form) + ' filings on SEC EDGAR</a> \u00b7 demo analysis is illustrative.</p>';
    var log = $('crawl-log'), items = panelBody.querySelectorAll('.stage');
    var seq = [];
    stages.forEach(function (s, i) {
      seq.push({ stage: i, start: true });
      s.lines.forEach(function (ln, k) { seq.push({ stage: i, line: ln, chip: s.chips ? k : -1 }); });
      if (s.chips && s.chips.length > s.lines.length) for (var c = s.lines.length; c < s.chips.length; c++) seq.push({ stage: i, chip: c });
      seq.push({ stage: i, end: true });
    });
    var i = 0, delay = reduceMotion ? 0 : 230;
    function step() {
      if (token !== panelToken) return;
      if (i >= seq.length) { $('report-card').classList.add('visible'); return; }
      var s = seq[i++], el = items[s.stage];
      if (s.start) { el.classList.add('on'); el.querySelector('.st').textContent = 'running'; }
      if (s.line) { var d = document.createElement('div'); d.className = s.line[0]; d.textContent = s.line[1]; log.appendChild(d); log.scrollTop = log.scrollHeight; }
      if (s.chip >= 0) { var ch = el.querySelectorAll('.chip')[s.chip]; if (ch) ch.classList.add('on'); }
      if (s.end) { el.classList.remove('on'); el.classList.add('done'); el.querySelector('.st').textContent = 'done'; el.querySelectorAll('.chip').forEach(function (c) { c.classList.add('on'); }); }
      if (delay) setTimeout(step, delay); else step();
    }
    step();
  }
  panelBody.addEventListener('click', function (e) {
    var g = e.target.closest('[data-goto]');
    if (g) { setTab(g.getAttribute('data-goto')); return; }
    var chip = e.target.closest('[data-filter]');
    if (chip && activeFiling) { diffFilter = chip.getAttribute('data-filter'); renderDiff(activeFiling.filing, activeFiling.ticker); var c2 = panelBody.querySelector('[data-filter="' + diffFilter + '"]'); if (c2) c2.focus(); return; }
    var tog = e.target.closest('[data-toggle]');
    if (tog) {
      var det = $(tog.getAttribute('aria-controls'));
      var open = tog.getAttribute('aria-expanded') !== 'true';
      tog.setAttribute('aria-expanded', String(open));
      det.hidden = !open;
    }
  });

  function renderDiff(f, t) {
    var diffs = diffsFor(f, t);
    function count(ty) { return diffs.filter(function (d) { return d.type === ty; }).length; }
    var shown = diffs.filter(function (d) { return diffFilter === 'all' || d.type === diffFilter; });
    panelBody.innerHTML = '<div class="diff-head">Comparing <b>' + esc(f.id) + '</b> with the prior ' + esc(f.form) + '</div>' +
      '<div class="diff-chips" role="group" aria-label="Filter changes">' +
      [['all', 'All', diffs.length], ['added', 'Added', count('added')], ['changed', 'Changed', count('changed')], ['removed', 'Removed', count('removed')]].map(function (c) {
        return '<button type="button" class="diff-chip" data-filter="' + c[0] + '" aria-pressed="' + (diffFilter === c[0]) + '">' + c[1] + ' (' + c[2] + ')</button>';
      }).join('') + '</div>' +
      (shown.length ? shown.map(function (d, i) {
        var has = d.before || d.after, id = 'dd-' + i;
        return '<div class="diff-item"><button type="button" ' + (has ? 'data-toggle aria-expanded="false" aria-controls="' + id + '"' : 'disabled') + '>' +
          '<span class="diff-badge ' + d.type + '">' + d.type.toUpperCase() + '</span>' +
          '<span><span class="diff-sec">' + esc(d.section) + '</span><br><span class="diff-txt">' + esc(d.text) + '</span></span>' +
          (has ? '<svg class="diff-caret" viewBox="0 0 24 24" width="16" height="16" aria-hidden="true"><path d="M6 9l6 6 6-6" stroke="currentColor" stroke-width="1.8" fill="none" stroke-linecap="round"/></svg>' : '') + '</button>' +
          (has ? '<div class="diff-detail" id="' + id + '" hidden>' +
            (d.before ? '<div class="diff-before"><span class="lbl">BEFORE</span>' + esc(d.before) + '</div>' : '') +
            (d.after ? '<div class="diff-after"><span class="lbl">AFTER</span>' + esc(d.after) + '</div>' : '') + '</div>' : '') + '</div>';
      }).join('') : '<p class="panel-foot">No ' + esc(diffFilter) + ' passages in this filing.</p>');
  }

  function renderScore(f, t) {
    var mat = Math.round(f.materiality * 100), burial = Math.round((f.burial || 0.35) * 100), gap = Math.round((f.gap || 0.44) * 100);
    var rank = mat >= 70 ? 'CRITICAL' : mat >= 50 ? 'HIGH' : mat >= 30 ? 'MEDIUM' : 'LOW';
    var col = { CRITICAL: '#ff8f8f', HIGH: '#f6c177', MEDIUM: '#a5adff', LOW: '#6ee7b7' }[rank];
    var C = 2 * Math.PI * 58;
    var rows = [['Volume delta', Math.round(mat * 0.5)], ['Hedging shift', Math.round(mat * 0.3)], ['Specificity', Math.round(mat * 0.2)], ['Tier weight', TIER1[f.form] ? 100 : 55]];
    panelBody.innerHTML = '<div class="ring-wrap"><svg width="140" height="140" viewBox="0 0 140 140" aria-hidden="true"><circle class="ring-bg" cx="70" cy="70" r="58" stroke-width="10"/>' +
      '<circle class="ring-fg" id="ring-fg" cx="70" cy="70" r="58" stroke-width="10" stroke="' + col + '" stroke-dasharray="' + C.toFixed(1) + '" stroke-dashoffset="' + C.toFixed(1) + '"/></svg>' +
      '<div class="ring-c"><b style="color:' + col + '">' + mat + '</b><span>/ 100 materiality</span></div></div>' +
      '<span class="rank" style="color:' + col + '">' + rank + '</span>' +
      '<div class="stats"><div class="stat"><b style="color:' + col + '">' + mat + '</b><span>Materiality</span></div>' +
      '<div class="stat"><b class="' + (burial >= 50 ? 'c-amber' : 'c-green') + '">' + burial + '</b><span>Burial</span></div>' +
      '<div class="stat"><b class="' + (gap >= 50 ? 'c-amber' : 'c-green') + '">' + gap + '</b><span>Attention gap</span></div></div>' +
      '<div class="rows">' + rows.map(function (r) { return '<div class="row"><span>' + r[0] + '</span><span class="track"><i data-w="' + (r[1] / 100) + '"></i></span><b>' + r[1] + '</b></div>'; }).join('') + '</div>' +
      '<p class="panel-foot">Materiality: how significant the disclosure changes are. Burial: how deep key information sits in footnotes. Attention gap: how far market coverage lags the change.</p>';
    requestAnimationFrame(function () { requestAnimationFrame(function () {
      var ring = $('ring-fg'); if (ring) ring.style.strokeDashoffset = (C - mat / 100 * C).toFixed(1);
      panelBody.querySelectorAll('.track i').forEach(function (el) { el.style.transform = 'scaleX(' + el.getAttribute('data-w') + ')'; });
    }); });
  }

  /* =====================================================================
   * AI WORKSPACE
   * ===================================================================== */
  var input = $('chat-input'), composer = $('composer'), thread = $('ws-thread'), messages = $('chat-messages');
  var busy = null; // {stop: fn}

  function autosize() { input.style.height = 'auto'; input.style.height = Math.min(input.scrollHeight, 120) + 'px'; }
  input.addEventListener('input', autosize);
  input.addEventListener('keydown', function (e) { if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) { e.preventDefault(); submit(); } });
  composer.addEventListener('submit', function (e) { e.preventDefault(); submit(); });

  var modeBtns = Array.prototype.slice.call(document.querySelectorAll('.modes [role="radio"]'));
  function setMode(m, focus) {
    mode = m;
    modeBtns.forEach(function (b) { var on = b.getAttribute('data-mode') === m; b.setAttribute('aria-checked', String(on)); b.tabIndex = on ? 0 : -1; if (on && focus) b.focus(); });
    input.placeholder = m === 'research' ? 'Research a question across filings\u2026' : m === 'report' ? 'Describe the report to generate (or just press Enter)\u2026' : (activeStock ? 'Ask about ' + activeStock + ' filings, or type "add MSFT"' : 'Ask about any filing, or type "add NVDA"');
  }
  modeBtns.forEach(function (b, i) {
    b.addEventListener('click', function () { setMode(b.getAttribute('data-mode')); });
    b.addEventListener('keydown', function (e) {
      var j = (e.key === 'ArrowRight' || e.key === 'ArrowDown') ? (i + 1) % modeBtns.length : (e.key === 'ArrowLeft' || e.key === 'ArrowUp') ? (i - 1 + modeBtns.length) % modeBtns.length : -1;
      if (j >= 0) { e.preventDefault(); setMode(modeBtns[j].getAttribute('data-mode'), true); }
    });
  });
  document.querySelectorAll('.tool').forEach(function (b) {
    b.addEventListener('click', function () { input.value = b.getAttribute('data-prompt'); autosize(); submit(); });
  });

  $('ws-collapse').addEventListener('click', function () {
    var collapsed = thread.classList.toggle('collapsed');
    this.textContent = collapsed ? 'Show thread' : 'Hide thread';
    this.setAttribute('aria-expanded', String(!collapsed));
  });

  /* attachments: analyzed locally in the browser, never uploaded */
  var fileInput = $('file-input');
  $('attach-btn').addEventListener('click', function () { fileInput.click(); });
  fileInput.addEventListener('change', function () { if (fileInput.files[0]) addAttachment(fileInput.files[0]); fileInput.value = ''; });
  ['dragenter', 'dragover'].forEach(function (ev) { composer.addEventListener(ev, function (e) { if (e.dataTransfer && Array.prototype.indexOf.call(e.dataTransfer.types, 'Files') >= 0) { e.preventDefault(); composer.classList.add('dragging'); } }); });
  ['dragleave', 'drop'].forEach(function (ev) { composer.addEventListener(ev, function (e) { if (ev === 'dragleave' && composer.contains(e.relatedTarget)) return; composer.classList.remove('dragging'); }); });
  composer.addEventListener('drop', function (e) { e.preventDefault(); var f = e.dataTransfer.files && e.dataTransfer.files[0]; if (f) addAttachment(f); });

  function addAttachment(file) {
    if (file.size > 15 * 1048576) { aiMessage({ text: 'That file is ' + fmtKB(file.size) + '. The demo analyzes files up to 15 MB.' }); return; }
    var ext = (file.name.split('.').pop() || '').toLowerCase();
    var att = { name: file.name, size: file.size, ext: ext, words: null, hints: [] };
    attachments = [att];
    renderAttachments();
    if (/^(txt|htm|html|xml|xbrl|json)$/.test(ext) && file.text) {
      file.slice(0, 2 * 1048576).text().then(function (txt) {
        var plain = ext === 'txt' ? txt : txt.replace(/<[^>]+>/g, ' ');
        att.words = (plain.match(/\b[\w'-]+\b/g) || []).length;
        if (/item\s+1a/i.test(plain)) att.hints.push('Item 1A risk factors');
        if (/item\s+7\b/i.test(plain)) att.hints.push('Item 7 MD&A');
        if (/ix:nonfraction|ix:header/i.test(txt)) att.hints.push('inline XBRL tags');
        if (/ownershipDocument/i.test(txt)) att.hints.push('Form 4 ownership XML');
        renderAttachments();
      }).catch(function () {});
    }
    input.focus();
  }
  function renderAttachments() {
    $('attachments').innerHTML = attachments.map(function (a, i) {
      return '<span class="att"><span>' + esc(a.name) + '</span><small>' + fmtKB(a.size) + (a.words ? ' \u00b7 ' + a.words.toLocaleString() + ' words' : '') + '</small>' +
        '<button type="button" data-rm-att="' + i + '" aria-label="Remove attachment ' + esc(a.name) + '">&times;</button></span>';
    }).join('');
  }
  $('attachments').addEventListener('click', function (e) { var b = e.target.closest('[data-rm-att]'); if (b) { attachments.splice(+b.getAttribute('data-rm-att'), 1); renderAttachments(); input.focus(); } });

  function showThread() { thread.hidden = false; thread.classList.remove('collapsed'); $('ws-collapse').textContent = 'Hide thread'; $('ws-collapse').setAttribute('aria-expanded', 'true'); }
  function addMsg(role, html) {
    showThread();
    var d = document.createElement('div');
    d.className = 'msg ' + role;
    d.innerHTML = '<div class="av" aria-hidden="true">' + (role === 'user' ? 'YOU' : 'AI') + '</div><div class="bubble">' + html + '</div>';
    messages.appendChild(d);
    messages.scrollTop = messages.scrollHeight;
    return d.querySelector('.bubble');
  }
  function setBusy(b) { busy = b; composer.classList.toggle('busy', !!b); $('send-btn').setAttribute('aria-label', b ? 'Stop generating' : 'Send message'); }

  function typewrite(el, text, done) {
    var sr = document.createElement('span');
    el.appendChild(sr);
    if (reduceMotion) { sr.textContent = text; if (done) setTimeout(done, 0); return { stop: function () {} }; }
    var i = 0, cur = document.createElement('span'); cur.className = 'cursor'; cur.setAttribute('aria-hidden', 'true');
    el.appendChild(cur);
    var iv = setInterval(function () {
      i = Math.min(text.length, i + 3);
      sr.textContent = text.slice(0, i);
      messages.scrollTop = messages.scrollHeight;
      if (i >= text.length) finish();
    }, 16);
    function finish() { clearInterval(iv); sr.textContent = text; if (cur.parentNode) cur.remove(); if (done) done(); }
    return { stop: finish };
  }

  function aiMessage(o) {
    var b = addMsg('ai', o.kicker ? '<span class="kicker">' + esc(o.kicker) + '</span>' : '');
    if (o.html) { b.insertAdjacentHTML('beforeend', o.html); if (o.done) o.done(b); return; }
    setBusy(typewrite(b, o.text, function () { setBusy(null); if (o.after) b.insertAdjacentHTML('beforeend', o.after); if (o.done) o.done(b); }));
  }

  function submit() {
    if (busy) { busy.stop(); setBusy(null); return; }
    var msg = input.value.trim();
    if (!msg && !attachments.length && mode !== 'report') return;
    if (!msg && mode === 'report') msg = 'Generate a disclosure report' + (activeStock ? ' for ' + activeStock : '');
    var atts = attachments.slice();
    addMsg('user', esc(msg || 'Analyze this document') + (atts.length ? '<br><small class="mono" style="color:#949db2">\u2295 ' + esc(atts[0].name) + '</small>' : ''));
    input.value = ''; autosize();
    attachments = []; renderAttachments();
    setTimeout(function () { respond(msg, atts); }, reduceMotion ? 0 : 450);
  }

  function respond(msg, atts) {
    var q = msg.toLowerCase();
    var cmd = q.match(/^(add|watch|track|remove|drop)\s+([a-z.]{1,6})\b/);
    if (cmd) {
      var t = cmd[2].toUpperCase().replace('.', '');
      if (!TICKER_DB[t]) { aiMessage({ text: t + ' is not in the demo universe yet. Try one of: ' + Object.keys(TICKER_DB).join(', ') + '.' }); return; }
      if (/add|watch|track/.test(cmd[1])) { addStock(t); aiMessage({ text: 'Added ' + t + ' (' + TICKER_DB[t].name + '). The crawler is discovering its filings now. Watch the hive grow and click any node to analyze it.' }); }
      else { removeStock(t); aiMessage({ text: 'Removed ' + t + ' from your watchlist.' }); }
      return;
    }
    if (/load demo|demo hive/.test(q)) { loadDemo(); aiMessage({ text: 'Loading a demo hive of five companies. Shared shareholders and deals will start linking the clusters as they appear.' }); return; }
    if (atts.length) { respondDoc(atts[0], msg); return; }
    if (!activeStock) {
      aiMessage({ text: 'Add a company first so I have filings to work with. Type "add NVDA", search the watchlist, or load the demo hive.', after: '<div class="actions"><button type="button" class="btn btn-ghost btn-sm" data-act="demo">Load demo hive</button><button type="button" class="btn btn-ghost btn-sm" data-act="add-NVDA">Add NVDA</button></div>' });
      return;
    }
    if (mode === 'research') return respondResearch(msg);
    if (mode === 'report') return respondReport(msg);
    respondChat(q);
  }

  function respondChat(q) {
    var t = activeStock, f = activeFiling ? activeFiling.filing : currentFiling(t), text;
    var insiders = getFilings(t).filter(function (x) { return x.form === 'Form 4' || x.form === 'Form 144'; }).length;
    if (/insider|form 4|144|ownership/.test(q)) text = AI_RESPONSES.insider(t, insiders);
    else if (/diff|change|prior|vs\b/.test(q)) text = AI_RESPONSES.diff(t, diffsFor(f, t));
    else if (q.indexOf('revenue') >= 0 || q.indexOf('growth') >= 0) text = AI_RESPONSES.revenue(t);
    else if (q.indexOf('risk') >= 0 || q.indexOf('factor') >= 0) text = AI_RESPONSES.risk(t);
    else if (q.indexOf('margin') >= 0 || q.indexOf('profit') >= 0) text = AI_RESPONSES.margin(t);
    else if (q.indexOf('guid') >= 0 || q.indexOf('target') >= 0 || q.indexOf('outlook') >= 0) text = AI_RESPONSES.guidance(t);
    else text = AI_RESPONSES['default'](t);
    aiMessage({ text: text, after: citesHtml(t, 2), done: function () {
      if (activeFiling) { panel.classList.add('open'); setTab('diff'); }
    } });
  }

  function topFilings(t, n) { return getFilings(t).slice().sort(function (a, b) { return b.materiality - a.materiality; }).slice(0, n); }
  function citesHtml(t, n) {
    return '<div class="cites" style="margin-top:8px">' + topFilings(t, n).map(function (f, i) {
      return '<button type="button" class="cite" data-cite="' + esc(t) + '|' + esc(f.id) + '">[' + (i + 1) + '] ' + esc(t + ' ' + f.id) + '</button>';
    }).join('') + '</div>';
  }

  function respondResearch(msg) {
    var t = activeStock, top = topFilings(t, 3);
    var plan = ['Pull ' + getFilings(t).length + ' ' + t + ' filings across 7 categories', 'Compare each against the prior period', 'Cross-check insider (Form 4) and proxy (DEF 14A) activity', 'Synthesize findings with citations'];
    var b = addMsg('ai', '<span class="kicker">Research mode \u00b7 ' + esc(t) + '</span><ol class="plan">' + plan.map(function (p) { return '<li>' + esc(p) + '</li>'; }).join('') + '</ol>');
    var lis = b.querySelectorAll('li'), i = 0, stopped = false;
    setBusy({ stop: function () { stopped = true; lis.forEach(function (l) { l.classList.add('done'); }); setBusy(null); } });
    (function tick() {
      if (stopped) return;
      if (i < lis.length) { lis[i++].classList.add('done'); setTimeout(tick, reduceMotion ? 0 : 520); return; }
      var d = diffsFor(top[0], t);
      var text = 'Across ' + t + '\'s recent filings, the highest-materiality document is ' + top[0].id + ' (' + Math.round(top[0].materiality * 100) + '/100). ' +
        'The key change: ' + d[0].text + ' ' + (d[1] ? 'Also notable: ' + d[1].text + ' ' : '') +
        'Insider and proxy filings show no conflicting signal in the demo data. Question asked: "' + msg + '".';
      setBusy(typewrite(b, text, function () { setBusy(null); b.insertAdjacentHTML('beforeend', citesHtml(t, 3)); }));
    })();
  }

  function buildReport(t) {
    var s = TICKER_DB[t], f = currentFiling(t), diffs = diffsFor(f, t), fl = getFilings(t);
    var byCat = {}; fl.forEach(function (x) { byCat[x.cat] = (byCat[x.cat] || 0) + 1; });
    var today = new Date().toISOString().slice(0, 10);
    return { t: t, s: s, f: f, diffs: diffs, fl: fl, byCat: byCat, today: today, top: topFilings(t, 3) };
  }
  function reportHtml(R) {
    return '<div class="report"><h3>' + esc(R.t) + ' disclosure brief</h3><p class="mono" style="font-size:11.5px;color:#949db2">' + esc(R.s.name) + ' \u00b7 ' + R.today + ' \u00b7 ' + R.fl.length + ' filings \u00b7 illustrative</p>' +
      '<h4>Summary</h4><p>' + esc(R.diffs[0].text) + '</p>' +
      '<h4>Material changes</h4><ul>' + R.diffs.slice(0, 3).map(function (d, i) { return '<li>' + esc(d.text) + ' <span class="mono" style="color:#e3c08a">[' + (i + 1) + ']</span></li>'; }).join('') + '</ul>' +
      '<h4>Coverage</h4><p>' + CAT_ORDER.filter(function (c) { return R.byCat[c]; }).map(function (c) { return esc(CATEGORIES[c].label) + ': ' + R.byCat[c]; }).join(' \u00b7 ') + '</p>' +
      '<h4>Scores (' + esc(R.f.id) + ')</h4><p>Materiality ' + Math.round(R.f.materiality * 100) + ' \u00b7 Burial ' + Math.round(R.f.burial * 100) + ' \u00b7 Attention gap ' + Math.round(R.f.gap * 100) + '</p>' +
      '<h4>Sources</h4>' + citesHtml(R.t, 3) +
      '<div class="actions"><button type="button" class="btn btn-ghost btn-sm" data-act="dl">Download .md</button><button type="button" class="btn btn-ghost btn-sm" data-act="copy">Copy</button></div></div>';
  }
  function reportMd(R) {
    return '# ' + R.t + ' disclosure brief\n\n' + R.s.name + ' | ' + R.today + ' | ' + R.fl.length + ' filings | ILLUSTRATIVE DEMO DATA, NOT INVESTMENT ADVICE\n\n' +
      '## Summary\n\n' + R.diffs[0].text + '\n\n## Material changes\n\n' + R.diffs.slice(0, 3).map(function (d, i) { return '- ' + d.text + ' [' + (i + 1) + ']'; }).join('\n') +
      '\n\n## Scores (' + R.f.id + ')\n\n- Materiality: ' + Math.round(R.f.materiality * 100) + '\n- Burial: ' + Math.round(R.f.burial * 100) + '\n- Attention gap: ' + Math.round(R.f.gap * 100) +
      '\n\n## Sources\n\n' + R.diffs.slice(0, 3).map(function (d, i) { return '[' + (i + 1) + '] ' + R.t + ' ' + R.f.id + ', ' + d.section; }).join('\n') + '\n';
  }
  var lastReport = null;
  function respondReport() {
    var R = buildReport(activeStock);
    lastReport = R;
    var b = addMsg('ai', '<span class="kicker">Report mode \u00b7 generating</span>');
    var stopped = false;
    setBusy({ stop: function () { stopped = true; setBusy(null); } });
    setTimeout(function () {
      if (stopped) { b.insertAdjacentHTML('beforeend', '<p>Report generation stopped.</p>'); return; }
      setBusy(null);
      b.querySelector('.kicker').textContent = 'Report mode \u00b7 ready';
      b.insertAdjacentHTML('beforeend', reportHtml(R));
      messages.scrollTop = messages.scrollHeight;
    }, reduceMotion ? 0 : 1100);
  }

  function respondDoc(a, msg) {
    var kind = a.ext === 'pdf' ? 'PDF' : /htm/.test(a.ext) ? 'HTML' : /xml|xbrl/.test(a.ext) ? 'XML/XBRL' : a.ext.toUpperCase() || 'file';
    var text = 'Parsed "' + a.name + '" locally in your browser (' + fmtKB(a.size) + ', ' + kind + (a.words ? ', ' + a.words.toLocaleString() + ' words' : '') + '). ' +
      (a.hints.length ? 'Detected: ' + a.hints.join(', ') + '. ' : (kind === 'PDF' ? 'PDF text extraction runs server-side in the full product. ' : 'No standard SEC item headings found. ')) +
      'In the full product this document would run through the same pipeline: parse, then financial, risk, historical-diff and forensic agents, then a cited report' +
      (activeStock ? ' compared against ' + activeStock + '\'s latest filings.' : '.') + ' Nothing was uploaded.';
    aiMessage({ kicker: 'Document analysis', text: text });
  }

  function explainEntity(d) {
    aiMessage({ kicker: 'Shared link \u00b7 ' + ENTITY_TYPES[d.etype].label, text: d.label + ' connects ' + d.tickers.join(', ') + ' (' + d.note.toLowerCase() + '). In the full product, a material change in one of these companies\' filings would flag the linked companies for review. This relationship is illustrative demo data.' });
  }

  messages.addEventListener('click', function (e) {
    var c = e.target.closest('[data-cite]');
    if (c) {
      var p = c.getAttribute('data-cite').split('|'), t = p[0];
      var f = getFilings(t).filter(function (x) { return x.id === p[1]; })[0];
      if (f) { if (pinned.indexOf(t) < 0) addStock(t, { instant: true }); openPanel(f, t); }
      return;
    }
    var a = e.target.closest('[data-act]');
    if (!a) return;
    var act = a.getAttribute('data-act');
    if (act === 'demo') loadDemo();
    else if (act.indexOf('add-') === 0) addStock(act.slice(4));
    else if ((act === 'dl' || act === 'copy') && lastReport) {
      var md = reportMd(lastReport);
      if (act === 'dl') {
        var url = URL.createObjectURL(new Blob([md], { type: 'text/markdown' }));
        var l = document.createElement('a'); l.href = url; l.download = lastReport.t + '-disclosure-brief.md'; document.body.appendChild(l); l.click(); l.remove();
        setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
      } else if (navigator.clipboard) {
        navigator.clipboard.writeText(md).then(function () { a.textContent = 'Copied'; }, function () { a.textContent = 'Copy failed'; });
      }
    }
  });

  /* =====================================================================
   * INIT
   * ===================================================================== */
  initGraph();
  setMode('chat');
  var fromUrl = (new URLSearchParams(location.search).get('t') || '').toUpperCase().split(',').filter(function (t) { return TICKER_DB[t]; });
  var saved = store(WL_KEY);
  var initial = fromUrl.length ? fromUrl : (Array.isArray(saved) ? saved.filter(function (t) { return TICKER_DB[t]; }) : []);
  initial.forEach(function (t) { addStock(t, { instant: true }); });
  renderSidebar();
  updateTopbar();
  setIdleStatus();
  updateGraph();
})();
