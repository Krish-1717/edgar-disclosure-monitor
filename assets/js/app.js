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
    'PYPL': {name:'PayPal Holdings', price:68.94, change:-1.5, sector:'Financials', cik:'0001633917', exchange:'NASDAQ'},
    'TSM': {name:'Taiwan Semiconductor Mfg.', price:172.40, change:1.6, sector:'Technology', cik:'0001046179', exchange:'NYSE', foreign:true},
    'ASML': {name:'ASML Holding N.V.', price:948.10, change:-0.6, sector:'Technology', cik:'0000937966', exchange:'NASDAQ', foreign:true},
    'XQRN': {name:'Quorenix Biotherapeutics (fictional)', price:24.18, change:6.4, sector:'Healthcare', cik:null, exchange:'DEMO', fictional:true},
    'XHLD': {name:'Helidyne Holdings (fictional)', price:11.07, change:-4.2, sector:'Industrials', cik:null, exchange:'DEMO', fictional:true}
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
   * FILING TAXONOMY (full catalog lives in assets/js/filings.js)
   * ===================================================================== */
  var F = window.EDM_FILINGS;
  var CATEGORIES = F.CATEGORIES, CAT_ORDER = F.CAT_ORDER, TIERS = F.TIERS;
  function tierOf(form) { return F.tierOf(form); }
  function formInfo(form) { return F.BY_CODE[form] || { code: form, name: form, desc: '', cats: ['financial'], cat: 'financial', tier: 0 }; }

  var ENTITY_TYPES = {
    holder: {label:'Shared shareholder', color:'#f5c97a'},
    exec:   {label:'Shared executive / director', color:'#67e8f9'},
    deal:   {label:'Shared deal', color:'#f9a8d4'}
  };
  // Illustrative relationships for the demo network. Not factual claims.
  var SHARED_ENTITIES = [
    {key:'vanguard', type:'holder', label:'Vanguard Group', note:'Passive holder reported on Schedule 13G', tickers:'*'},
    {key:'blackrock', type:'holder', label:'BlackRock', note:'Passive holder reported on Schedule 13G', tickers:'*'},
    {key:'berkshire', type:'holder', label:'Berkshire Hathaway', note:'Position reported on Form 13F-HR', tickers:['AAPL','BAC','V','MA','AMZN','BRKB']},
    {key:'foundry', type:'deal', label:'Foundry supply agreements', note:'Shared supplier named in risk factors', tickers:['NVDA','AAPL','AMD','TSM']},
    {key:'litho', type:'deal', label:'Lithography equipment supply', note:'Supplier relationship described in 20-F', tickers:['ASML','TSM']},
    {key:'aicloud', type:'deal', label:'AI compute capacity deals', note:'Customer and supplier relationships disclosed in 8-Ks', tickers:['NVDA','MSFT','GOOGL','AMZN','META']},
    {key:'cards', type:'deal', label:'Card network partnerships', note:'Commercial agreements', tickers:['V','MA','PYPL','JPM','BAC']},
    {key:'pharma', type:'deal', label:'Pharmacy benefit contracts', note:'Commercial relationships', tickers:['LLY','UNH']},
    {key:'streaming', type:'deal', label:'Cloud hosting agreement', note:'Vendor relationship', tickers:['NFLX','AMZN']},
    {key:'energy', type:'deal', label:'Materials offtake agreements', note:'Supply agreements', tickers:['TSLA','XOM']},
    {key:'merger', type:'deal', label:'Pending merger', note:'Quorenix proposes to acquire Helidyne (fictional companies)', tickers:['XQRN','XHLD']},
    {key:'underwriter', type:'deal', label:'IPO underwriting', note:'Lead underwriter on the S-1 (fictional issuer)', tickers:['XQRN','GS','JPM']},
    {key:'board-tech', type:'exec', label:'Board interlock', note:'Director serving on several boards', tickers:['GOOGL','NFLX','META']},
    {key:'board-fin', type:'exec', label:'Board interlock', note:'Director serving on several boards', tickers:['JPM','GS','XOM']},
    {key:'exec-move', type:'exec', label:'Executive move', note:'Former officer now at a peer company', tickers:['TSLA','NKE','AAPL']},
    {key:'activist', type:'holder', label:'Activist fund', note:'Schedule 13D filer pushing for board seats (fictional)', tickers:['XQRN','XHLD']}
  ];

  function D(type, section, text, before, after) { return { type: type, section: section, text: text, before: before || null, after: after || null }; }
  var CATEGORY_DIFFS = {
    governance: function () { return [
      D('changed','Compensation Discussion & Analysis','CEO pay ratio moved and a new performance metric was added to long-term incentives.','Long-term incentive awards vest based on relative TSR.','Long-term incentive awards vest based on relative TSR and a new free-cash-flow margin goal.'),
      D('added','Proposal 4','New shareholder proposal on AI governance and disclosure.',null,'Shareholders request a report on the oversight of artificial intelligence risks by the Board...'),
      D('removed','Board Diversity Matrix','One independent director did not stand for re-election.','The Board consists of 12 directors, 11 of whom are independent.',null)]; },
    insider: function () { return [
      D('added','Table I \u00b7 Non-Derivative Securities','Officer sale of common stock under a Rule 10b5-1 trading plan.',null,'Code S \u00b7 12,500 shares \u00b7 weighted average price disclosed in footnote (1).'),
      D('changed','Beneficial ownership','Direct holdings after the transaction fell versus the prior filing.','Amount owned following reported transaction: 412,300 (D)','Amount owned following reported transaction: 399,800 (D)')]; },
    offerings: function () { return [
      D('added','Use of Proceeds','Registration covers shares reserved for the employee equity plan.',null,'The shares registered hereby are issuable under the Company\'s Amended and Restated Equity Incentive Plan...'),
      D('changed','Plan share reserve','Share reserve increased versus the prior registration.','Up to 25,000,000 shares','Up to 40,000,000 shares')]; },
    ma: function () { return [
      D('added','Background of the Transaction','New disclosure of the deal timeline and board deliberations.',null,'On several occasions during the quarter, representatives of the parties discussed a potential business combination...'),
      D('changed','Exchange ratio','Consideration terms amended from the prior communication.','0.42 shares per target share','0.45 shares per target share plus cash in lieu of fractional shares')]; },
    debt: function () { return [
      D('added','Item 2.03 \u00b7 Direct Financial Obligation','New senior unsecured notes and a revolving credit facility amendment.',null,'The Company entered into an amendment extending the maturity of its $5.0 billion revolving credit facility to 2029...'),
      D('changed','Covenants','Maximum leverage covenant loosened versus the prior agreement.','Consolidated leverage ratio not to exceed 3.25 to 1.00','Consolidated leverage ratio not to exceed 3.75 to 1.00')]; },
    specialized: function () { return [
      D('changed','Specialized disclosure','Scope of the specialized report changed versus the prior year.','Covers 214 suppliers in scope.','Covers 238 suppliers in scope; 3 smelters newly identified.')]; },
    other: function () { return [
      D('changed','Prepared remarks','Management tone on demand moved from cautious to confident.','"We remain cautious on the second half."','"We are seeing broad-based strength heading into the second half."'),
      D('added','Q&A','New disclosure in analyst Q&A not present in the written release.',null,'"We expect capital expenditures to step up meaningfully next year."')]; }
  };
  var FORM_DIFFS = {
    '20-F': [D('added','Item 3.D \u00b7 Risk Factors','New geopolitical and export-control risk language.',null,'Tensions across the Taiwan Strait and export controls may disrupt our operations and customers...'), D('changed','Item 5 \u00b7 Operating Review','Capacity guidance raised for advanced nodes.','We expect moderate capacity growth.','We expect to significantly expand advanced-node capacity.')],
    '6-K': [D('added','Monthly revenue report','Monthly revenue up year over year; board approved capital appropriations.',null,'Net revenue for the month increased 33.9% year over year...')],
    'S-1': [D('added','Prospectus Summary','Initial registration of common stock for the IPO.',null,'We are offering 12,000,000 shares of our common stock. This is our initial public offering...'), D('added','Risk Factors','Going-concern and single-product dependency risks disclosed.',null,'We have a limited operating history and depend on the success of our lead product candidate...')],
    'NT 10-K': [D('added','Part III \u00b7 Narrative','Company cannot file its 10-K on time and cites an ongoing review of revenue recognition.',null,'The Registrant requires additional time to complete its review of certain revenue recognition matters...')],
    'NT 10-Q': [D('added','Part III \u00b7 Narrative','Late quarterly filing notice; auditor review not complete.',null,'The Registrant was unable to complete its quarterly review without unreasonable effort or expense...')],
    'SC TO-T': [D('added','Item 4 \u00b7 Terms of the Transaction','Third party offers to buy all outstanding shares at a premium.',null,'Offer to purchase all outstanding shares at $14.25 net per share in cash...')],
    'SC 14D9': [D('added','Item 4 \u00b7 The Solicitation or Recommendation','Target board recommends that shareholders tender their shares.',null,'The Board unanimously recommends that stockholders accept the Offer and tender their Shares...')],
    'SC 13D': [D('added','Item 4 \u00b7 Purpose of Transaction','Holder discloses activist intentions, seeking board seats.',null,'The Reporting Persons intend to engage with the Board regarding strategic alternatives and board composition...')],
    'DEFC14A': [D('added','Contested solicitation','Dissident slate of three director nominees.',null,'We are soliciting your proxy to elect our three highly qualified nominees...')],
    '15-12B': [D('added','Certification','Notice of termination of registration after the merger closes.',null,'Certification and notice of termination of registration under Section 12(b)...')],
    '15-12G': [D('added','Certification','Suspension of reporting obligations.',null,'Certification and notice of termination of registration under Section 12(g)...')],
    '13F-HR': [D('changed','Information table','Quarterly holdings: top position trimmed, two new positions added.','Top position: 915.6M shares','Top position: 789.4M shares')],
    '13F-NT': [D('added','Notice','Holdings are reported by another manager on its 13F-HR.',null,'This report is a notice; all holdings are reported by other reporting managers...')],
    '10-D': [D('changed','Distribution report','Delinquencies in the asset pool ticked up.','60+ day delinquencies: 0.82%','60+ day delinquencies: 0.97%')],
    'ABS-EE': [D('added','Asset-level data','Asset-level exhibit filed for the trust.',null,'EX-102 asset data file covering 184,233 receivables...')]
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
    if (!info || !info.cik) return null;
    var type = form ? form.replace(/^Form /, '') : '';
    if (formInfo(form).cat === 'other') type = '';
    return 'https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=' + info.cik + '&type=' + encodeURIComponent(type) + '&dateb=&owner=include&count=40';
  }
  function cikOf(t) { var c = TICKER_DB[t].cik; return c || ('09' + String(hash(t) % 100000000).padStart(8, '0')); }

  /* ---------- real SEC data: static feeds written by the ORACLE crawler ----------
   * `python -m oracle export --out assets/data/oracle` (see README). Tickers with a feed
   * show real Tier 1 filings (10-K, 10-Q, 8-K, DEF 14A, Form 4) with real section changes;
   * everything else, and every ticker without a feed, stays illustrative. If the feeds
   * can't be fetched (offline, file://) the app silently falls back to the demo data. */
  var LIVE_BASE = 'assets/data/oracle/';
  var LIVE_ALIAS = { BRKB: 'BRK-B' };
  var LIVE_FORMS = { '10-K': 1, '10-Q': 1, '8-K': 1, 'DEF 14A': 1, 'Form 4': 1 };
  var LIVE_SECTION = { risk_factors: 'Risk Factors', mdna: 'MD&A', market_risk: 'Market Risk', financial_statements: 'Financial Statements' };
  var LIVE_WEIGHT = { risk_factors: 2, mdna: 2, market_risk: 1, financial_statements: 1 };
  var LIVE = {}, liveIndex = null, livePending = {}, liveGeneratedAt = null;
  function liveFetchJson(url) {
    if (!window.fetch) return Promise.reject(new Error('no fetch'));
    return fetch(url, { cache: 'no-cache' }).then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); });
  }
  function liveListed(t) { return !!(liveIndex && liveIndex[LIVE_ALIAS[t] || t]); }
  function liveLoad(t) {
    if (LIVE[t] || !liveListed(t)) return Promise.resolve();
    if (!livePending[t]) {
      livePending[t] = liveFetchJson(LIVE_BASE + liveIndex[LIVE_ALIAS[t] || t]).then(function (feed) {
        if (feed && feed.filings && feed.filings.length) { LIVE[t] = feed; delete filingCache[t]; }
      }).catch(function () { /* keep demo data */ });
    }
    return livePending[t];
  }
  function liveInit(tickers) {
    var timeout = new Promise(function (res) { setTimeout(res, 3000); });
    var load = liveFetchJson(LIVE_BASE + 'index.json').then(function (idx) {
      liveIndex = {};
      liveGeneratedAt = idx.generated_at || null;
      (idx.companies || []).forEach(function (c) { liveIndex[c.ticker] = c.feed; });
      return Promise.all(tickers.map(liveLoad));
    }).catch(function () { liveIndex = liveIndex || {}; });
    return Promise.race([load, timeout]);
  }
  function liveFilings(t) {
    var r = rng(hash(t + 'live'));
    return LIVE[t].filings.filter(function (x) { return x.status === 'fetched'; }).map(function (x) {
      var code = /^[345]$/.test(x.base_form) ? 'Form ' + x.base_form : x.base_form, fi = formInfo(code);
      var label = code + (x.is_amendment ? '/A' : '');
      var w = 0, sum = 0;
      (x.sections || []).forEach(function (sec) { if (sec.change) { var k = LIVE_WEIGHT[sec.key] || 1; w += k; sum += k * sec.change.change_ratio; } });
      var mat = w ? sum / w : (fi.tier === 1 ? 0.3 : 0.2);
      return {
        id: label + x.id.slice(x.form.length), form: code, date: x.date, cat: fi.cat, group: fi.cat, current: !!x.current,
        materiality: +Math.min(0.99, mat).toFixed(2), burial: +(0.1 + r() * 0.45).toFixed(2), gap: +(0.1 + r() * 0.5).toFixed(2),
        live: true, measured: w > 0, accession: x.accession, sec_url: x.sec_url, index_url: x.index_url, sha256: x.sha256, version: x.version,
        is_amendment: x.is_amendment, amends: x.amends_accession, compared_to: x.compared_to, items: x.items || [], sections: x.sections || []
      };
    });
  }
  function liveQuote(p) { var q = p.length > 110 ? p.slice(0, 107).replace(/\s+\S*$/, '') + '\u2026' : p; return '\u201c' + q + '\u201d'; }
  function liveDiffs(f) {
    var out = [], prior = 'the prior ' + f.form, rank = { risk_factors: 0, mdna: 1, market_risk: 2, financial_statements: 3 };
    f.sections.slice().sort(function (a, b) { return (a.key in rank ? rank[a.key] : 9) - (b.key in rank ? rank[b.key] : 9); }).forEach(function (sec) {
      var c = sec.change, name = LIVE_SECTION[sec.key] || sec.title, where = sec.item.replace(/ \(.*\)$/, '') + ' \u00b7 ' + name;
      if (!c) return;
      c.added_samples.forEach(function (p, i) {
        out.push({ type: 'added', section: where, before: null, after: p,
          text: i ? 'New: ' + liveQuote(p) : c.paragraphs_added + ' new paragraph' + (c.paragraphs_added === 1 ? '' : 's') + ' in ' + name + ' vs ' + prior + '.' });
      });
      c.modified_samples.forEach(function (m) {
        out.push({ type: 'changed', section: where, before: m.before, after: m.after,
          text: 'Reworded passage in ' + name + ' (' + Math.round(m.similarity * 100) + '% word overlap with ' + prior + ').' });
      });
      c.removed_samples.forEach(function (p, i) {
        out.push({ type: 'removed', section: where, before: p, after: null,
          text: i ? 'Dropped: ' + liveQuote(p) : c.paragraphs_removed + ' paragraph' + (c.paragraphs_removed === 1 ? '' : 's') + ' dropped from ' + name + ' vs ' + prior + '.' });
      });
    });
    if (out.length) return out;
    var first = f.sections[0];
    if (first && !f.compared_to) {
      return [{ type: 'added', section: first.item.replace(/ \(.*\)$/, '') + ' \u00b7 ' + (LIVE_SECTION[first.key] || first.title), before: null, after: first.excerpt,
        text: 'Earliest ' + f.form + ' in the crawl window, so there is no prior version to compare yet. ' + f.sections.length + ' sections extracted.' }];
    }
    if (first) return [{ type: 'changed', section: f.form, before: null, after: null, text: 'No wording changes detected vs ' + prior + ' (numbers only).' }];
    return [{ type: 'added', section: formInfo(f.form).name, before: null, after: null,
      text: f.form + ' filed ' + f.date + (f.items.length ? ' \u00b7 Items ' + f.items.join(', ') : '') + '. Open it on SEC EDGAR for the full document.' }];
  }

  /* ---------- filing set per ticker: base FILING_DATA + seeded filings across all 8 categories ---------- */
  var filingCache = {};
  var FORCE = { NVDA: ['Form 5', 'Form 144'], AAPL: ['SD', 'DEFA14A', 'S-8'], MSFT: ['S-3', '11-K'], GS: ['13F-NT', '13F-HR'], BRKB: ['13F-HR'], JPM: ['13F-HR', '10-D', 'ABS-EE'], BAC: ['13F-HR', '10-D', 'ABS-EE'] };
  var FICTIONAL_SETS = {
    // IPO-stage biotech that also launches an acquisition: offerings, new insiders, activism, a late filing
    XQRN: [['S-1', { current: true, mat: 0.82, m: 1 }], ['424B3', { mat: 0.55 }], ['424B5', { mat: 0.5 }], ['Form 3'], ['Form 3'], ['Form 3'], ['Form 4'], ['Form 4'],
      ['10-Q', { mat: 0.48 }], ['10-Q', { mat: 0.4 }], ['8-K', { label: '8-K Item 5.02', item: '5.02', mat: 0.58 }], ['DEF 14A'], ['PRE 14A'], ['DEFC14A', { mat: 0.71 }],
      ['SC 13D', { mat: 0.74 }], ['NT 10-Q', { mat: 0.62 }], ['S-4', { mat: 0.8 }], ['425'], ['425'], ['EX-99 Earnings'], ['Transcript'], ['Investor Deck'], ['Letter'], ['EX-10']],
    // Target of a tender offer and merger, then deregistration
    XHLD: [['10-K', { current: true, mat: 0.7, m: 2 }], ['10-Q', { mat: 0.45 }], ['NT 10-K', { mat: 0.72 }], ['8-K', { label: '8-K Item 1.01', item: '1.01', cat: 'ma', mat: 0.78 }],
      ['8-K', { label: '8-K Item 2.03', item: '2.03', cat: 'debt', mat: 0.52 }], ['SC TO-T', { mat: 0.8 }], ['SC 14D9', { mat: 0.68 }], ['SC TO-I', { mat: 0.4 }], ['PREM14A', { mat: 0.55 }],
      ['DEFM14A', { mat: 0.7 }], ['DEF 14C'], ['425'], ['15-12B', { mat: 0.6 }], ['15-12G', { mat: 0.5 }], ['Form 4'], ['SC 13G'], ['SC 13D', { mat: 0.66 }], ['EX-4 Debt'], ['Rating', { mat: 0.5 }], ['ARS']]
  };
  function getFilings(t) {
    if (filingCache[t]) return filingCache[t];
    var r = rng(hash(t)), info = TICKER_DB[t], fin = info.sector === 'Financials';
    var list = [], used = {}, has = {}, live = !!LIVE[t] && !info.fictional;
    function push(f) { var n = 2, id = f.id; while (used[id]) id = f.id + ' #' + n++; used[id] = 1; f.id = id; has[f.form] = 1; list.push(f); }
    function add(form, o) {
      if (live && LIVE_FORMS[form]) return;      // real filings cover this form
      o = o || {};
      var fi = formInfo(form), m = o.m != null ? o.m : Math.floor(r() * 11), yr = o.y || 24, cat = o.cat || fi.cat;
      push({ id: (o.label || form) + ' ' + MONTHS[m] + '\'' + yr, form: form, item: o.item || null, date: MONTHS[m] + ' ' + (1 + Math.floor(r() * 27)) + ', 20' + yr,
        cat: cat, group: cat, current: !!o.current,
        materiality: +(o.mat != null ? o.mat : 0.12 + r() * 0.45).toFixed(2), burial: +(0.1 + r() * 0.45).toFixed(2), gap: +(0.1 + r() * 0.5).toFixed(2) });
    }
    function maybe(p, form, o) { if (r() < p) add(form, o); }
    var i;
    if (info.fictional) {
      FICTIONAL_SETS[t].forEach(function (x) { add(x[0], x[1]); });
    } else if (info.foreign) {
      add('20-F', { current: true, m: 3, mat: 0.66 }); add('20-F', { m: 3, y: 23, mat: 0.5 });
      for (i = 0; i < 4; i++) add('6-K', { mat: 0.2 + r() * 0.4 });
      add(t === 'TSM' ? 'F-1' : 'F-3', { mat: 0.3 });
      add('SC 13G');
      add('EX-99 Earnings'); add('EX-99 Earnings'); add('Transcript'); add('Transcript'); add('Investor Deck'); add('Rating'); add('EX-10');
    } else {
      if (live) liveFilings(t).forEach(push);
      else (FILING_DATA[t] || FILING_DATA.DEFAULT).forEach(function (f) { var c = {}; for (var k in f) c[k] = f[k]; c.cat = 'financial'; push(c); });
      maybe(0.6, '8-K', { label: '8-K Item 2.03', item: '2.03', cat: 'debt', mat: 0.3 + r() * 0.3 });
      maybe(0.25, '8-K', { label: '8-K Item 1.01', item: '1.01', cat: 'ma', mat: 0.4 + r() * 0.35 });
      add('DEF 14A', { mat: 0.35 + r() * 0.3 });
      maybe(0.55, 'DEFA14A'); maybe(0.15, 'PRE 14A');
      var n4 = 2 + Math.floor(r() * 3);
      for (i = 0; i < n4; i++) add('Form 4', { mat: 0.15 + r() * 0.45 });
      maybe(0.35, 'Form 3'); maybe(0.3, 'Form 5'); maybe(0.5, 'Form 144');
      add('SC 13G', { mat: 0.18 + r() * 0.2 });
      maybe(0.6, 'S-8'); maybe(0.3, 'S-3'); maybe(0.25, '424B5'); maybe(0.2, '424B3');
      if (fin || r() < 0.3) { add('424B2'); add('FWP'); }
      maybe(0.12, 'SC TO-I');
      if (info.sector === 'Technology' || info.sector === 'Consumer') maybe(0.75, 'SD');
      maybe(0.4, '11-K');
      add('ARS'); add('EX-99 Earnings'); add('EX-99 Earnings'); add('Earnings Deck'); add('Transcript'); add('Transcript');
      maybe(0.6, 'Investor Deck'); maybe(0.4, 'Letter'); maybe(0.5, 'EX-4 Debt'); add('Rating'); add('EX-10');
    }
    (FORCE[t] || []).forEach(function (form) { if (!has[form]) add(form); });
    filingCache[t] = list;
    return list;
  }
  function diffsFor(f, t) {
    if (f.live) return liveDiffs(f);
    if (FORM_DIFFS[f.form]) return FORM_DIFFS[f.form];
    if (f.cat === 'financial' && /^(10-K|10-Q|8-K)$/.test(f.form)) return DIFFS[t] || DIFFS.DEFAULT;
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
      if (LIVE[t] && LIVE[t].filings[0]) days = Math.max(0, Math.round((Date.now() - Date.parse(LIVE[t].filings[0].filing_date)) / 864e5));
      return '<div class="stock-card' + (t === activeStock ? ' active' : '') + '" data-t="' + t + '">' +
        '<button type="button" class="sc-main" data-select="' + t + '" aria-pressed="' + (t === activeStock) + '" aria-label="Focus ' + esc(s.name) + '">' +
        '<div class="sc-top"><span class="sc-ticker">' + t + '</span><span class="sc-change ' + (up ? 'up' : 'dn') + '">' + (up ? '+' : '') + s.change.toFixed(1) + '%</span></div>' +
        '<div class="sc-name">' + esc(s.name) + '</div>' +
        '<div class="sc-mid"><span class="sc-price">$' + s.price.toFixed(2) + '</span><span><span class="sc-badge">' + fl.length + ' filings</span><span class="sc-badge">' + days + 'd ago</span>' + (LIVE[t] ? '<span class="sc-badge sc-live" title="Real SEC filings crawled by ORACLE">SEC</span>' : '') + '</span></div>' +
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
  $('quick-add').innerHTML = ['NVDA', 'MSFT', 'TSM', 'JPM', 'XHLD'].map(function (t) { return '<button type="button" data-quick="' + t + '">' + t + '</button>'; }).join('');
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
    if (liveListed(t) && !LIVE[t] && !opts.liveTried) {
      liveLoad(t).then(function () { opts.liveTried = true; addStock(t, opts); });
      return true;
    }
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
    link.href = edgarUrl(activeStock, '') || 'https://www.sec.gov/edgar/search/';
  }

  /* =====================================================================
   * CRAWLER PIPELINE STRIP (presentation only)
   * ===================================================================== */
  var pipeToken = 0, pipeTicker = null;
  var stageEls = Array.prototype.slice.call(document.querySelectorAll('#pipeline li'));
  function setIdleStatus() {
    stageEls.forEach(function (el) { el.classList.remove('active'); });
    var n = pinned.reduce(function (a, t) { return a + getFilings(t).length; }, 0);
    $('pipeline-status').textContent = pinned.length ? 'Watching ' + pinned.length + ' compan' + (pinned.length === 1 ? 'y' : 'ies') + ' \u00b7 ' + n + ' filings indexed' : 'Idle \u00b7 waiting for a watchlist';
  }
  function runPipeline(t) {
    if (pipeTicker && pipeTicker !== t && pinned.indexOf(pipeTicker) >= 0) growTo(pipeTicker, getFilings(pipeTicker).length, 300);
    var token = ++pipeToken;
    pipeTicker = t;
    var fl = getFilings(t), total = fl.length, r = rng(hash(t + 'pipe'));
    var mb = (fl.length * 0.31 + (hash(t) % 9) / 10).toFixed(1);
    var nDiff = fl.reduce(function (a, f) { return a + diffsFor(f, t).length; }, 0);
    var cats = {}; fl.forEach(function (f) { cats[f.cat] = 1; });
    var steps = [
      { s: 0, text: t + ' \u00b7 discovering ' + total + ' accession numbers across ' + Object.keys(cats).length + ' categories\u2026', reveal: Math.ceil(total * 0.45),
        log: function () { return fl.slice(0, 6).map(function (f) { return ['k-disc', 'DISCOVER', t + ' ' + f.form + ' acc ' + accFor(f, t)]; }); } },
      { s: 1, text: t + ' \u00b7 retrieving ' + total + ' documents + exhibits (' + mb + ' MB)', reveal: total,
        log: function () { return [['k-get', 'FETCH', fl[0].form + ' ' + (300 + Math.floor(r() * 700)) + ' KB sha256:' + sha(t + 'a').slice(0, 10) + '\u2026'], ['k-get', 'FETCH', (6 + Math.floor(r() * 20)) + ' exhibits + XBRL instance'], ['k-dup', 'DEDUP', Math.floor(r() * 3) + ' duplicates skipped by hash'], ['k-retry', 'RETRY', 'HTTP 429 \u2192 backoff 2s \u2192 OK (limit 10 req/s)']]; } },
      { s: 2, text: t + ' \u00b7 extracting HTML \u00b7 iXBRL \u00b7 PDF \u00b7 XLSX',
        log: function () { return [['k-parse', 'EXTRACT', 'HTML ' + (40 + Math.floor(r() * 60)) + ' sections segmented'], ['k-parse', 'EXTRACT', 'iXBRL ' + (1500 + Math.floor(r() * 4000)) + ' facts \u00b7 concepts normalized'], ['k-parse', 'EXTRACT', (10 + Math.floor(r() * 30)) + ' tables rebuilt \u00b7 versions preserved']]; } },
      { s: 3, text: t + ' \u00b7 6 agents analyzing (financial, risk, diff, forensic, corporate, external)',
        log: function () { return F.AGENTS.map(function (a) { return ['k-agent', 'AGENT', a.name + ' \u00b7 ' + t + ' \u00b7 done']; }); } },
      { s: 4, text: t + ' \u00b7 cited report ready \u00b7 ' + nDiff + ' material changes',
        log: function () { return [['k-cite', 'REPORT', t + ' brief \u00b7 ' + nDiff + ' findings \u00b7 ' + (nDiff + 4) + ' citations']]; } }
    ];
    stageEls.forEach(function (el) { el.classList.remove('active', 'done'); });
    autoOpenConsole();
    var i = 0;
    function next() {
      if (token !== pipeToken) return;
      if (i > 0) { stageEls[steps[i - 1].s].classList.remove('active'); stageEls[steps[i - 1].s].classList.add('done'); }
      if (i >= steps.length) { setTimeout(function () { if (token === pipeToken) { stageEls.forEach(function (el) { el.classList.remove('done'); }); setIdleStatus(); } }, 2600); return; }
      var st = steps[i];
      stageEls[st.s].classList.add('active');
      $('pipeline-status').textContent = st.text;
      if (st.reveal) growTo(t, st.reveal, 760);
      st.log().forEach(function (l, k) { setTimeout(function () { if (token === pipeToken) consoleLine(l[0], l[1], l[2]); }, reduceMotion ? 0 : k * 120); });
      i++;
      setTimeout(next, reduceMotion ? 0 : 950);
    }
    next();
  }

  /* ---------- crawler console drawer ---------- */
  var consoleEl = $('crawl-console'), consoleLog = $('crawl-console-log'), consoleBtn = $('console-btn'), consoleUserSet = false, cStats = { docs: 0, dup: 0, cite: 0 };
  function setConsole(open, user) {
    if (user) consoleUserSet = true;
    consoleEl.hidden = !open;
    consoleBtn.setAttribute('aria-expanded', String(open));
  }
  function autoOpenConsole() { if (!consoleUserSet && window.innerWidth > 1100) setConsole(true); }
  consoleBtn.addEventListener('click', function () { setConsole(consoleEl.hidden, true); });
  $('console-close').addEventListener('click', function () { setConsole(false, true); consoleBtn.focus(); });
  function consoleLine(cls, kind, text) {
    if (kind === 'FETCH' || kind === 'DISCOVER') cStats.docs++;
    if (kind === 'DEDUP') cStats.dup++;
    if (kind === 'REPORT') cStats.cite++;
    var li = document.createElement('li');
    li.innerHTML = '<span class="k ' + cls + '">' + kind + '</span> ' + esc(text);
    consoleLog.appendChild(li);
    while (consoleLog.children.length > 40) consoleLog.removeChild(consoleLog.firstChild);
    consoleLog.scrollTop = consoleLog.scrollHeight;
    $('cc-stats').textContent = (6 + Math.random() * 3.8).toFixed(1) + ' req/s \u00b7 ' + cStats.docs + ' docs \u00b7 ' + cStats.dup + ' deduped \u00b7 ' + cStats.cite + ' reports';
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
    return d.tier === 1 ? 8.5 : d.tier === 2 ? 6.5 : 5;
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
      var fl = getFilings(t).slice(0, reveal[t] || 0).filter(visibleFiling);
      var cats = {};
      fl.forEach(function (f, k) {
        if (!cats[f.cat]) {
          var ci = CAT_ORDER.indexOf(f.cat), a = ci / CAT_ORDER.length * Math.PI * 2;
          cats[f.cat] = node('cat:' + t + ':' + f.cat, { kind: 'cat', ticker: t, cat: f.cat, tx: tg.x + Math.cos(a) * 60, ty: tg.y + Math.sin(a) * 60 }, hub);
          links.push({ id: 'hc:' + t + ':' + f.cat, source: hub.id, target: cats[f.cat].id, kind: 'hc', cat: f.cat });
        }
        var fn = node('f:' + t + ':' + f.id, { kind: 'filing', ticker: t, cat: f.cat, filing: f, tier: tierOf(f.form), tx: cats[f.cat].tx, ty: cats[f.cat].ty }, cats[f.cat]);
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
      function (en) { return en.append('line').attr('stroke', function (d) { return d.kind === 'hc' ? 'rgba(168,180,255,0.35)' : CATEGORIES[d.cat].color; })
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
        if (d.tier === 1) g.append('circle').attr('r', 12).attr('fill', 'none').attr('stroke', '#f5c97a').attr('stroke-opacity', 0.85).attr('stroke-width', 1.2).attr('filter', 'url(#soft-glow)');
        else if (d.tier === 2) g.append('circle').attr('r', 9).attr('fill', 'none').attr('stroke', c).attr('stroke-opacity', 0.55).attr('stroke-width', 0.9);
        g.append('circle').attr('class', 'core').attr('r', nodeR(d)).attr('fill', c).attr('fill-opacity', d.tier === 1 ? 0.95 : d.tier === 2 ? 0.85 : 0.65);
        if (d.tier === 1) g.append('text').text(d.filing.form.replace('Form ', 'F')).attr('text-anchor', 'middle').attr('dy', 23).attr('font-size', 8.5).attr('fill', '#98a2c4');
        g.append('circle').attr('class', 'focus-ring').attr('r', d.tier === 1 ? 16 : 11);
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
    applyHighlight();
    updateExplorer();
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
    var lg = $('legend'), left = (!lg.hidden && W > 900) ? lg.offsetWidth + 16 : 0, uw = W - left;
    var pad = 50, bw = Math.max(1, x1 - x0) + pad * 2, bh = Math.max(1, y1 - y0) + pad * 2;
    var k = Math.min(1.5, uw / bw, H / bh);
    var tx = left + uw / 2 - k * (x0 + x1) / 2, ty = H / 2 - k * (y0 + y1) / 2;
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
    else html = '<b>' + esc(d.filing.id) + '</b>' + (d.tier ? ' \u00b7 Tier ' + d.tier : '') + '<br>' + esc(formInfo(d.filing.form).name) + ' \u00b7 ' + esc(CATEGORIES[d.cat].label) + '<br>Filed ' + esc(d.filing.date) + ' \u00b7 Materiality ' + Math.round(d.filing.materiality * 100);
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

  /* ---------- coverage explorer (legend + filters + form finder) ---------- */
  var hiddenCats = {}, tierFilter = 'all', hlForm = null;
  function visibleFiling(f) {
    if (hiddenCats[f.cat]) return false;
    if (tierFilter === 'all') return true;
    var tr = tierOf(f.form);
    return tierFilter === 'std' ? !tr : String(tr) === tierFilter;
  }
  function watchCounts() {
    var byForm = {}, byCat = {};
    pinned.forEach(function (t) { getFilings(t).slice(0, reveal[t] || 0).forEach(function (f) { byForm[f.form] = (byForm[f.form] || 0) + 1; byCat[f.cat] = (byCat[f.cat] || 0) + 1; }); });
    return { byForm: byForm, byCat: byCat };
  }
  function renderLegend() {
    var lg = $('legend');
    lg.innerHTML = '<div class="cx-head"><h2>Coverage explorer</h2><span class="cx-sum mono" id="cx-sum"></span></div>' +
      '<div class="cx-tiers" role="group" aria-label="Filter by tier">' +
      [['all', 'All'], ['1', 'Tier 1'], ['2', 'Tier 2'], ['3', 'Tier 3'], ['std', 'Other']].map(function (x) {
        return '<button type="button" data-tier="' + x[0] + '" aria-pressed="' + (tierFilter === x[0]) + '">' + x[1] + '</button>';
      }).join('') + '</div>' +
      '<ul class="cx-cats">' + CAT_ORDER.map(function (c) {
        var C = CATEGORIES[c], forms = F.CATALOG.filter(function (f) { return f.cat === c; });
        return '<li><div class="cx-row"><label><input type="checkbox" data-cat="' + c + '" checked><i style="background:' + C.color + ';box-shadow:0 0 8px ' + C.color + '"></i>' + esc(C.label) + '</label>' +
          '<span class="cx-n mono" data-catn="' + c + '">0</span>' +
          '<button type="button" class="cx-exp" aria-expanded="false" aria-controls="cx-f-' + c + '" aria-label="Show ' + esc(C.label) + ' forms"><svg viewBox="0 0 24 24" width="14" height="14" aria-hidden="true"><path d="M6 9l6 6 6-6" stroke="currentColor" stroke-width="1.8" fill="none" stroke-linecap="round"/></svg></button></div>' +
          '<ul class="cx-forms" id="cx-f-' + c + '" hidden>' + forms.map(function (f) {
            return '<li><button type="button" data-form="' + esc(f.code) + '" aria-pressed="false"><span class="code mono' + (f.tier ? ' t' + f.tier : '') + '">' + esc(f.code) + '</span><span class="nm">' + esc(f.name) + '</span><span class="cx-n mono" data-formn="' + esc(f.code) + '">0</span></button></li>';
          }).join('') + '</ul></li>';
      }).join('') + '</ul>' +
      '<div class="cx-detail" id="cx-detail" aria-live="polite"></div>' +
      '<h2>Node key</h2><ul class="cx-key"><li><i class="k-t1"></i>Tier 1 &middot; essential</li><li><i class="k-t2"></i>Tier 2 &middot; advanced</li><li><i class="k-t3"></i>Tier 3 / other</li>' +
      Object.keys(ENTITY_TYPES).map(function (k) { return '<li class="shared-k"><i style="background:' + ENTITY_TYPES[k].color + '"></i>' + esc(ENTITY_TYPES[k].label) + '</li>'; }).join('') +
      '</ul><p>Relationships and filings are illustrative demo data.</p>';
    if (window.innerWidth < 900) toggleLegend(false);
    updateExplorer();
  }
  var exRaf = 0;
  function updateExplorer() {
    if (exRaf) return;
    exRaf = requestAnimationFrame(function () {
      exRaf = 0;
      var c = watchCounts(), present = Object.keys(c.byForm).filter(function (k) { return F.BY_CODE[k]; }).length;
      var sum = $('cx-sum'); if (!sum) return;
      sum.textContent = present + ' / ' + F.CATALOG.length + ' forms';
      document.querySelectorAll('[data-catn]').forEach(function (el) { el.textContent = c.byCat[el.getAttribute('data-catn')] || 0; });
      document.querySelectorAll('[data-formn]').forEach(function (el) { var n = c.byForm[el.getAttribute('data-formn')] || 0; el.textContent = n; el.parentNode.classList.toggle('none', !n); });
    });
  }
  function applyHighlight() {
    if (!hasD3 || !gNodes) return;
    gNodes.selectAll('g.node').classed('dim', function (d) { return !!hlForm && !(d.kind === 'filing' && d.filing.form === hlForm) && d.kind !== 'hub'; })
      .classed('hl', function (d) { return !!hlForm && d.kind === 'filing' && d.filing.form === hlForm; });
    gLinks.selectAll('line').classed('dim', !!hlForm);
    gShared.selectAll('line').classed('dim', !!hlForm);
  }
  $('legend').addEventListener('change', function (e) {
    var cb = e.target.closest('[data-cat]'); if (!cb) return;
    if (cb.checked) delete hiddenCats[cb.getAttribute('data-cat')]; else hiddenCats[cb.getAttribute('data-cat')] = 1;
    updateGraph();
  });
  $('legend').addEventListener('click', function (e) {
    var tb = e.target.closest('[data-tier]');
    if (tb) { tierFilter = tb.getAttribute('data-tier'); document.querySelectorAll('[data-tier]').forEach(function (b) { b.setAttribute('aria-pressed', String(b === tb)); }); updateGraph(); return; }
    var ex = e.target.closest('.cx-exp');
    if (ex) { var open = ex.getAttribute('aria-expanded') !== 'true'; ex.setAttribute('aria-expanded', String(open)); $(ex.getAttribute('aria-controls')).hidden = !open; return; }
    var fb = e.target.closest('[data-form]');
    if (fb) {
      var code = fb.getAttribute('data-form');
      hlForm = hlForm === code ? null : code;
      document.querySelectorAll('[data-form]').forEach(function (b) { b.setAttribute('aria-pressed', String(b.getAttribute('data-form') === hlForm)); });
      var det = $('cx-detail');
      if (!hlForm) { det.innerHTML = ''; applyHighlight(); return; }
      var fi = formInfo(code), n = watchCounts().byForm[code] || 0;
      det.innerHTML = '<b class="mono">' + esc(fi.code) + '</b> ' + esc(fi.name) + (fi.tier ? ' <span class="tb t' + fi.tier + '">Tier ' + fi.tier + '</span>' : '') + '<p>' + esc(fi.desc) + '</p>' +
        '<p class="mono">' + n + ' in your hive' + (fi.cats.length > 1 ? ' \u00b7 also ' + fi.cats.slice(1).map(function (c) { return CATEGORIES[c].short; }).join(', ') : '') + '</p>' +
        (n ? '<button type="button" class="btn btn-ghost btn-sm" data-open-form="' + esc(code) + '">Analyze first one</button>' : '<p class="muted">Add a company that files this form, e.g. ' + esc(suggestFor(code)) + '.</p>');
      applyHighlight();
      return;
    }
    var of = e.target.closest('[data-open-form]');
    if (of) {
      var code2 = of.getAttribute('data-open-form');
      for (var i = 0; i < pinned.length; i++) {
        var hit = getFilings(pinned[i]).slice(0, reveal[pinned[i]] || 0).filter(function (f) { return f.form === code2; })[0];
        if (hit) { if (activeStock !== pinned[i]) selectStock(pinned[i]); openPanel(hit, pinned[i]); return; }
      }
    }
  });
  function suggestFor(code) {
    var ks = Object.keys(TICKER_DB);
    for (var i = 0; i < ks.length; i++) if (getFilings(ks[i]).some(function (f) { return f.form === code; })) return ks[i];
    return 'XHLD';
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
  // Nine companies that together file every form in the catalog
  var DEMO_HIVE = ['NVDA', 'AAPL', 'MSFT', 'JPM', 'GS', 'TSM', 'ASML', 'XQRN', 'XHLD'];
  function loadDemo() {
    DEMO_HIVE.forEach(function (t, i) {
      setTimeout(function () { addStock(t, { instant: reduceMotion }); }, reduceMotion ? 0 : i * 1300);
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
    $('panel-sub').textContent = f.form + ' \u00b7 ' + formInfo(f.form).name + ' \u00b7 Filed ' + f.date + (tierOf(f.form) ? ' \u00b7 Tier ' + tierOf(f.form) : '');
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

  function sha(seed) { var r = rng(hash(seed)), s = ''; for (var i = 0; i < 64; i++) s += '0123456789abcdef'[Math.floor(r() * 16)]; return s; }
  function accFor(f, t) { if (f.accession) return f.accession; var r = rng(hash(t + f.id + 'acc')); return cikOf(t).slice(-7).replace(/^0+/, '') .padStart(7, '0') + '-' + f.date.slice(-2) + '-' + String(100000 + Math.floor(r() * 899999)); }
  function crawlStages(f, t) {
    var info = TICKER_DB[t], r = rng(hash(t + f.id)), fi = formInfo(f.form), cik = cikOf(t);
    var xml = f.cat === 'insider' && /^Form [345]$/.test(f.form), other = f.cat === 'other';
    var acc = accFor(f, t), kb = Math.round(300 + r() * 700), diffs = diffsFor(f, t);
    var amended = r() < 0.15;
    var stages = [
      { key: 'discover', label: 'Discover', chips: ['EDGAR full-index', 'Submissions API', 'Bulk archive', 'CIK map', 'Amendments'], lines: [
        ['l-info', '> Poll daily index + submissions API for CIK ' + cik + (info.cik ? '' : ' (demo)')],
        ['l-ok', '> Resolved ' + t + ' \u2192 ' + info.name + ' (ticker + historical names mapped)'],
        ['l-ok', '> New accession ' + acc + ' \u00b7 ' + f.form + ' \u00b7 ' + fi.name],
        [amended ? 'l-warn' : 'l-mut', amended ? '> Amendment detected: superseding prior version' : '  no prior amendment on record']] },
      { key: 'retrieve', label: 'Retrieve', chips: ['Primary doc', 'Exhibits', 'XBRL', 'Dedupe', 'Retry', '\u226410 req/s'], lines: [
        ['l-info', '> GET primary document \u00b7 ' + kb + ' KB ' + (xml ? 'XML' : other ? 'PDF' : 'HTML')],
        ['l-info', '> GET ' + (xml ? 1 : 4 + Math.floor(r() * 12)) + ' exhibits + attachments' + (xml || other ? '' : ' + XBRL instance')],
        ['l-mut', '  scheduler: fair-access 10 req/s \u00b7 User-Agent declared'],
        [r() < 0.3 ? 'l-warn' : 'l-mut', r() < 0.3 ? '> HTTP 429 \u2192 exponential backoff 2s \u2192 retried OK' : '  dedupe: sha256 unseen \u00b7 stored']] },
      { key: 'extract', label: 'Extract', chips: xml ? ['XML ownership'] : other ? ['PDF', 'Transcript text', 'Tables'] : ['HTML', 'iXBRL', 'PDF', 'XLSX', 'Exhibits'], lines: xml ? [
        ['l-ok', '> XML: ownership document \u00b7 ' + (1 + Math.floor(r() * 4)) + ' transactions \u00b7 codes S, M, A'],
        ['l-mut', '  footnotes linked to Table I rows']] : [
        ['l-ok', '> ' + (other ? 'PDF/text' : 'HTML') + ': ' + (f.live && f.sections.length ? f.sections.length + ' target' : 8 + Math.floor(r() * 12)) + ' sections segmented'],
        ['l-ok', other ? '> Speaker turns + Q&A separated' : '> iXBRL: ' + (600 + Math.floor(r() * 1400)) + ' tagged facts (us-gaap, dei)'],
        ['l-ok', '> ' + (3 + Math.floor(r() * 9)) + ' financial tables reconstructed \u00b7 concepts normalized'],
        ['l-mut', '  footnotes, risk factors, MD&A and material agreements indexed']] },
      { key: 'analyze', label: 'Analyze', chips: F.AGENTS.map(function (a) { return a.name; }), lines: [
        ['l-info', '> Financial: key metrics reconciled to XBRL facts'],
        ['l-info', '> Risk: ' + diffs.filter(function (d) { return d.type === 'added'; }).length + ' new disclosures flagged'],
        ['l-info', '> Historical diff: ' + diffs.length + ' material passages vs prior version'],
        [f.burial > 0.45 ? 'l-warn' : 'l-mut', '> Forensic: burial ' + Math.round(f.burial * 100) + (f.burial > 0.45 ? ' \u00b7 key detail sits in footnotes' : ' \u00b7 no anomalies')],
        ['l-info', '> Corporate intel: ' + (2 + Math.floor(r() * 5)) + ' linked executives, holders or deals'],
        ['l-info', '> External research: cross-checked ' + (1 + Math.floor(r() * 4)) + ' outside sources']] },
      { key: 'report', label: 'Cited report', chips: ['Summary', 'Changes', 'Risks', 'Capital structure', 'Citations'], lines: [
        ['l-warn', '> Materiality ' + Math.round(f.materiality * 100) + '/100 \u00b7 ' + (f.materiality >= 0.7 ? 'HIGH' : f.materiality >= 0.5 ? 'MEDIUM' : 'LOW')],
        ['l-ok', '> \u2713 Report ready \u00b7 every finding cites filing, period and page']] }
    ];
    if (f.live) {   // real ORACLE crawl: report what v0 actually did, not the simulated extras
      var nSec = f.sections.length, nCmp = f.sections.filter(function (x) { return x.change; }).length;
      stages[0].lines[3] = f.is_amendment ? ['l-warn', '> Amendment v' + f.version + (f.amends ? ' of ' + f.amends : '') + ' \u00b7 original kept'] : ['l-mut', '  original filing (v1)'];
      stages[1].lines = [
        ['l-info', '> GET primary document ' + f.sec_url.split('/').pop()],
        ['l-info', '> GET filing index (index.json): every exhibit and XBRL file listed'],
        ['l-mut', '  scheduler: 8 req/s (SEC cap 10) \u00b7 User-Agent declared \u00b7 backoff on 429/5xx'],
        ['l-mut', '  dedupe: sha256 ' + String(f.sha256 || '').slice(0, 12) + '\u2026 stored']];
      stages[2].lines = nSec ? [
        ['l-ok', '> HTML \u2192 text: ' + nSec + ' target sections segmented (' + f.sections.map(function (x) { return LIVE_SECTION[x.key] || x.title; }).join(', ') + ')'],
        ['l-mut', '  table of contents + running page headers suppressed'],
        ['l-mut', '  iXBRL facts and exhibits: not extracted in v0']] : [
        ['l-ok', '> ' + (xml ? 'XML ownership document' : 'Document') + ' stored as filed'],
        ['l-mut', '  section extraction runs on 10-K / 10-Q only in v0']];
      stages[3].lines = [
        nCmp ? ['l-info', '> Historical diff: ' + nCmp + ' sections compared with ' + f.compared_to] : ['l-mut', '  no prior ' + f.form + ' in the crawl window to compare'],
        ['l-info', '> ' + diffs.length + ' passages surfaced (added / reworded / removed)'],
        ['l-mut', '  other agents: illustrative in this demo']];
      stages[4].lines = [
        f.measured ? ['l-warn', '> Change score ' + Math.round(f.materiality * 100) + '/100 \u00b7 share of paragraphs changed'] : ['l-mut', '  change score: n/a (nothing to compare)'],
        ['l-ok', '> \u2713 Report ready \u00b7 cites ' + f.accession]];
    }
    return stages;
  }

  function renderCrawler(f, t) {
    var token = panelToken;
    var stages = crawlStages(f, t), diffs = diffsFor(f, t), fi = formInfo(f.form), info = TICKER_DB[t];
    var secs = (1.4 + (hash(f.id + t) % 30) / 10).toFixed(1), acc = accFor(f, t), url = edgarUrl(t, f.form);
    var src = f.live ? f.sec_url : info.cik ? 'https://www.sec.gov/Archives/edgar/data/' + String(+info.cik) + '/' + acc.replace(/-/g, '') + '/' : 'demo://' + t.toLowerCase() + '/' + acc;
    panelBody.innerHTML =
      '<p class="form-desc"><b>' + esc(fi.name) + '.</b> ' + esc(fi.desc) + '</p>' +
      '<ol class="stages">' + stages.map(function (s, i) {
        return '<li class="stage" data-i="' + i + '"><div class="stage-h"><span>' + esc(s.label) + '</span><span class="st">queued</span></div>' +
          '<div class="chips">' + s.chips.map(function (c) { return '<span class="chip">' + esc(c) + '</span>'; }).join('') + '</div></li>';
      }).join('') + '</ol>' +
      '<div class="log" id="crawl-log" role="log" aria-label="Crawler log"></div>' +
      '<div class="report-card" id="report-card"><h3>Cited summary</h3><p>' + esc(diffs[0].text) + '</p>' +
      '<div class="cites">' + diffs.slice(0, 3).map(function (d, i) { return '<button type="button" class="cite" data-goto="diff">[' + (i + 1) + '] ' + esc(d.section) + '</button>'; }).join('') + '</div>' +
      '<div class="stats"><div class="stat"><b class="' + matClass(f.materiality) + '">' + Math.round(f.materiality * 100) + '</b><span>Materiality</span></div>' +
      '<div class="stat"><b class="c-amber">' + diffs.length + '</b><span>Changes</span></div>' +
      (f.live ? '<div class="stat"><b class="c-accent">' + f.sections.length + '</b><span>Sections</span></div></div>'
        : '<div class="stat"><b class="c-accent">' + secs + 's</b><span>Crawl time</span></div></div>') +
      '<dl class="prov"><dt>Source</dt><dd class="mono">' + esc(src) + '</dd><dt>SHA-256</dt><dd class="mono">' + (f.sha256 || sha(t + f.id)).slice(0, 32) + '\u2026</dd>' +
      '<dt>Period</dt><dd>' + esc(f.date) + '</dd><dt>Version</dt><dd>' + (f.live ? 'v' + f.version + (f.is_amendment && f.amends ? ' \u00b7 amends ' + esc(f.amends) : ' \u00b7 original') : 'v1 \u00b7 original preserved') + '</dd></dl></div>' +
      (f.live
        ? '<p class="panel-foot"><span class="live-tag">Real SEC filing</span> <a href="' + esc(f.index_url || f.sec_url) + '" target="_blank" rel="noopener">Open ' + esc(f.accession) + ' on SEC EDGAR</a> \u00b7 Crawled by ORACLE. ' + (f.measured ? 'Materiality here is the measured share of changed paragraphs; burial and attention gap are illustrative.' : 'No earlier version to compare, so the scores are placeholders.') + '</p>'
        : '<p class="panel-foot">' + (url ? '<a href="' + url + '" target="_blank" rel="noopener">View ' + esc(t) + ' ' + esc(f.form) + ' filings on SEC EDGAR</a> \u00b7 ' : 'Fictional demo company: no EDGAR record. ') + 'Demo analysis is illustrative.</p>');
    var log = $('crawl-log'), items = panelBody.querySelectorAll('.stage'), seq = [];
    stages.forEach(function (s, i) {
      seq.push({ stage: i, start: true });
      var n = Math.max(s.lines.length, s.chips.length);
      for (var k = 0; k < n; k++) seq.push({ stage: i, line: s.lines[k], chip: k < s.chips.length ? k : -1 });
      seq.push({ stage: i, end: true });
    });
    var i = 0, delay = reduceMotion ? 0 : 140;
    function step() {
      if (token !== panelToken) return;
      if (i >= seq.length) { $('report-card').classList.add('visible'); return; }
      var s = seq[i++], el = items[s.stage];
      if (s.start) { el.classList.add('on'); el.querySelector('.st').textContent = 'running'; }
      if (s.line) { var d = document.createElement('div'); d.className = s.line[0]; d.textContent = s.line[1]; log.appendChild(d); log.scrollTop = log.scrollHeight; }
      if (s.chip >= 0) { var ch = el.querySelectorAll('.chip')[s.chip]; if (ch) ch.classList.add('on'); }
      if (s.end) { el.classList.remove('on'); el.classList.add('done'); el.querySelector('.st').textContent = 'done'; }
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
    panelBody.innerHTML = '<div class="diff-head">' + (f.live && !f.compared_to ? 'No earlier ' + esc(f.form) + ' in the crawl window for <b>' + esc(f.id) + '</b>'
      : 'Comparing <b>' + esc(f.id) + '</b> with the prior ' + esc(f.form)) + (f.live ? ' <span class="live-tag">Real SEC text</span>' : '') + '</div>' +
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
    var rows = [['Volume delta', Math.round(mat * 0.5)], ['Hedging shift', Math.round(mat * 0.3)], ['Specificity', Math.round(mat * 0.2)], ['Tier weight', [45, 100, 75, 55][tierOf(f.form)]]];
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
    var fm = findForm(msg);
    if (fm && mode === 'chat' && /what|explain|mean|is a|tell me|define|which|\?/.test(q)) { respondForm(fm); return; }
    if (!activeStock) {
      aiMessage({ text: 'Add a company first so I have filings to work with. Type "add NVDA", search the watchlist, or load the demo hive.', after: '<div class="actions"><button type="button" class="btn btn-ghost btn-sm" data-act="demo">Load demo hive</button><button type="button" class="btn btn-ghost btn-sm" data-act="add-NVDA">Add NVDA</button></div>' });
      return;
    }
    if (mode === 'research') return respondResearch(msg);
    if (mode === 'report') return respondReport(msg);
    respondChat(q);
  }

  function findForm(msg) {
    var up = ' ' + msg.toUpperCase().replace(/[^A-Z0-9 \-\/]/g, ' ') + ' ', best = null;
    F.CATALOG.forEach(function (f) {
      var codes = [f.code.toUpperCase()];
      if (/^FORM /.test(codes[0])) codes.push(codes[0].replace('FORM ', ''));
      if (/^SC /.test(codes[0])) codes.push('SCHEDULE ' + codes[0].slice(3));
      codes.forEach(function (c) { if (c.length > 1 && up.indexOf(' ' + c + ' ') >= 0 && (!best || c.length > best.len)) best = { f: f, len: c.length }; });
    });
    return best && best.f;
  }
  function respondForm(f) {
    var holders = pinned.filter(function (t) { return getFilings(t).some(function (x) { return x.form === f.code; }); });
    var text = f.code + ' (' + f.name + '): ' + f.desc + ' Category: ' + f.cats.map(function (c) { return CATEGORIES[c].label; }).join(', ') + '. ' +
      (f.tier ? 'Priority: ' + TIERS[f.tier].label + ' (' + TIERS[f.tier].name + '). ' : '') +
      (holders.length ? 'In your hive: ' + holders.join(', ') + '. Pick it in the coverage explorer to highlight every ' + f.code + ' node.' : 'None in your hive yet. ' + suggestFor(f.code) + ' files one in the demo; type "add ' + suggestFor(f.code) + '".');
    aiMessage({ kicker: 'Filing guide', text: text });
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
    var plan = ['Pull ' + getFilings(t).length + ' ' + t + ' filings across ' + Object.keys(getFilings(t).reduce(function (a, f) { a[f.cat] = 1; return a; }, {})).length + ' categories', 'Compare each against the prior period', 'Cross-check insider (Form 4) and proxy (DEF 14A) activity', 'Synthesize findings with citations'];
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
  renderSidebar();
  updateTopbar();
  setIdleStatus();
  updateGraph();
  liveInit(initial).then(function () {
    initial.forEach(function (t) { addStock(t, { instant: true, liveTried: true }); });
    renderSidebar();
    updateTopbar();
    setIdleStatus();
    updateGraph();
  });
})();
