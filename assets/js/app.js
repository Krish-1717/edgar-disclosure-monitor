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
  function formInfo(form) { return F.BY_CODE[form] || { code: form, name: form, desc: 'SEC form ' + form + '.', cats: ['specialized'], cat: 'specialized', tier: 0 }; }

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
      text: f.form + (f.is_amendment ? '/A' : '') + ' filed ' + f.date + (f.items.length ? ' \u00b7 Items ' + itemNames(f.items).join('; ') : '') + (f.desc && f.desc.toUpperCase() !== f.form.toUpperCase() ? ' \u00b7 ' + f.desc : '') + '. Not deep-parsed yet: open it on SEC EDGAR for the full document.' }];
  }


  /* ---------- live SEC data for ANY public company ----------
   * data.sec.gov/submissions sends Access-Control-Allow-Origin: *, so the visitor's browser
   * reads the real filing history of every SEC registrant directly (no backend). The list of
   * all ~10,000 SEC-listed tickers ships as assets/data/oracle/universe.json (written by
   * `python -m oracle universe`). Deep parsing (sections, diffs) comes from the ORACLE feeds. */
  var SEC_SUBMISSIONS = 'https://data.sec.gov/submissions/';
  var HIVE_PER_FORM = 8, HIVE_MAX = 64;
  var FORM_ALIAS = { '3': 'Form 3', '4': 'Form 4', '5': 'Form 5', '144': 'Form 144', 'SCHEDULE 13G': 'SC 13G', 'SCHEDULE 13D': 'SC 13D' };
  var ITEM_8K = { '1.01': 'Material agreement', '1.02': 'Agreement terminated', '1.03': 'Bankruptcy', '1.05': 'Cybersecurity incident', '2.01': 'Acquisition or disposition completed',
    '2.02': 'Results of operations', '2.03': 'New financial obligation', '2.04': 'Obligation accelerated', '2.05': 'Exit or restructuring costs', '2.06': 'Impairment',
    '3.01': 'Listing notice', '3.02': 'Unregistered equity sale', '3.03': 'Rights of holders modified', '4.01': 'Auditor change', '4.02': 'Non-reliance on prior financials',
    '5.01': 'Change in control', '5.02': 'Officer or director change', '5.03': 'Charter or bylaw amendment', '5.07': 'Shareholder vote results', '5.08': 'Director nominations',
    '7.01': 'Regulation FD disclosure', '8.01': 'Other events', '9.01': 'Financial statements and exhibits' };
  var SEC = {}, UNIVERSE = null, universeRows = [], universeLoading = null;
  function pad10(c) { return String(+c).padStart(10, '0'); }
  function fmtDate(iso) { var p = String(iso || '').split('-'); return p.length === 3 ? MONTHS[+p[1] - 1] + ' ' + (+p[2]) + ', ' + p[0] : String(iso || ''); }
  function daysAgo(iso) { return Math.max(0, Math.round((Date.now() - Date.parse(iso)) / 864e5)); }
  var KEEP_UPPER = { AG: 1, SA: 1, NV: 1, SE: 1, PLC: 1, LLC: 1, LP: 1, LTD: 1, REIT: 1, ETF: 1, USA: 1, US: 1, NEC: 1, ADR: 1, II: 1, III: 1, IV: 1, AI: 1, NA: 1 };
  var NICE = { INC: 'Inc.', CORP: 'Corp.', CO: 'Co.', LTD: 'Ltd.', PLC: 'plc', HOLDINGS: 'Holdings', AND: 'and', OF: 'of', THE: 'the', FOR: 'for', IN: 'in' };
  function titleCase(s) {
    s = String(s || '').replace(/\s*\/[A-Z]{2,3}\/?\s*$/, '').trim();   // drop EDGAR state suffixes like "/DE/" or "/NEW"
    if (/[a-z]/.test(s)) return s;                                         // already mixed case: keep the filer's own casing
    return s.split(/(\s+|-|&|,)/).map(function (w, i) {
      var u = w.replace(/[.,]/g, '').toUpperCase();
      if (!/[A-Z]/.test(u)) return w;
      if (NICE[u] && (i > 0 || !/^(AND|OF|THE|FOR|IN)$/.test(u))) return NICE[u] + (w.slice(-1) === ',' ? ',' : '');
      if (KEEP_UPPER[u] || (u.length <= 3 && !/[AEIOU]/.test(u)) || /\d/.test(u) || u.length <= 2) return w.toUpperCase();
      return w.charAt(0).toUpperCase() + w.slice(1).toLowerCase();
    }).join('').replace(/\.\./g, '.');
  }
  function itemNames(items) { return items.map(function (i) { return i + (ITEM_8K[i] ? ' ' + ITEM_8K[i] : ''); }); }

  function loadUniverse() {
    if (!universeLoading) {
      universeLoading = liveFetchJson(LIVE_BASE + 'universe.json').then(function (u) {
        UNIVERSE = {};
        universeRows = u.companies || [];
        universeRows.forEach(function (r) { if (!UNIVERSE[r[0]]) UNIVERSE[r[0]] = r; });
      }).catch(function () { UNIVERSE = UNIVERSE || {}; });
    }
    return universeLoading;
  }
  function normTicker(t) { return String(t || '').trim().toUpperCase().replace(/\./g, '-'); }
  // Make sure a ticker has a TICKER_DB entry (featured demo entries keep theirs).
  function ensureTicker(t) {
    t = normTicker(t);
    if (TICKER_DB[t]) return t;
    if (TICKER_DB[t.replace(/-/g, '')]) return t.replace(/-/g, '');
    var r = UNIVERSE && UNIVERSE[t];
    if (!r) return null;
    TICKER_DB[t] = { name: r[1], cik: pad10(r[2]), exchange: r[3] || 'Unlisted', sector: '', universe: true };
    return t;
  }
  function isReal(t) { var s = TICKER_DB[t]; return !!(s && s.cik && !s.fictional); }

  function secLoad(t) {
    var info = TICKER_DB[t];
    if (!isReal(t)) return Promise.resolve();
    var s = SEC[t];
    if (s && s.status !== 'error') return s.promise;
    s = SEC[t] = { status: 'loading', filings: [], files: [], page: 0, started: Date.now() };
    s.url = SEC_SUBMISSIONS + 'CIK' + pad10(info.cik) + '.json';
    s.promise = liveFetchJson(s.url).then(function (d) {
      s.meta = { name: d.name, sic: d.sic, sicDescription: d.sicDescription, exchanges: d.exchanges || [], tickers: d.tickers || [],
        fiscalYearEnd: d.fiscalYearEnd, state: d.stateOfIncorporation, category: d.category, formerNames: d.formerNames || [] };
      s.filings = secRows(d.filings.recent, +info.cik);
      s.files = (d.filings.files || []).slice();
      s.status = 'ok';
      s.ms = Date.now() - s.started;
      if (!info.sector && d.sicDescription) info.sector = titleCase(d.sicDescription);
      if (info.universe && d.name) info.name = titleCase(d.name);
      delete filingCache[t];
    }).catch(function (e) { s.status = 'error'; s.error = String((e && e.message) || e); });
    return s.promise;
  }
  function secRows(r, cik) {
    var out = [], n = (r.accessionNumber || []).length;
    for (var i = 0; i < n; i++) {
      var raw = String(r.form[i] || ''), up = raw.toUpperCase(), amend = /\/A$/.test(up), base = amend ? up.slice(0, -2) : up;
      var code = FORM_ALIAS[base] || base, fi = formInfo(code), acc = r.accessionNumber[i], nd = acc.replace(/-/g, '');
      var doc = (r.primaryDocument && r.primaryDocument[i]) || '';
      if (/^xsl/i.test(doc.split('/')[0]) && doc.indexOf('/') > 0) doc = doc.split('/').pop();
      var folder = 'https://www.sec.gov/Archives/edgar/data/' + cik + '/' + nd + '/';
      out.push({ accession: acc, secForm: raw, code: code, amend: amend, cat: fi.cat, tier: F.BY_CODE[code] ? fi.tier : 0,
        date: r.filingDate[i], report: (r.reportDate && r.reportDate[i]) || '', doc: doc,
        desc: (r.primaryDocDescription && r.primaryDocDescription[i]) || '',
        items: r.items && r.items[i] ? String(r.items[i]).split(',').filter(Boolean) : [], size: (r.size && r.size[i]) || 0,
        url: doc ? folder + doc : folder, indexUrl: folder + acc + '-index.htm' });
    }
    return out;
  }
  function secLoadOlder(t) {
    var s = SEC[t];
    if (!s || s.status !== 'ok' || s.page >= s.files.length) return Promise.resolve(false);
    return liveFetchJson(SEC_SUBMISSIONS + s.files[s.page].name).then(function (d) {
      s.filings = s.filings.concat(secRows(d, +TICKER_DB[t].cik));
      s.page++;
      return true;
    });
  }
  function placeholderMat(tier) { return tier === 1 ? 0.3 : tier === 2 ? 0.22 : 0.15; }
  function realFiling(t, r) {
    var lab = r.code + (r.amend ? '/A' : ''), p = r.date.split('-');
    return { id: lab + ' ' + MONTHS[+p[1] - 1] + ' \'' + p[0].slice(2), form: r.code, date: fmtDate(r.date), iso: r.date, cat: r.cat, group: r.cat,
      current: false, materiality: placeholderMat(r.tier), burial: 0.2, gap: 0.2, real: true, measured: false, accession: r.accession,
      sec_url: r.url, index_url: r.indexUrl, version: r.amend ? 2 : 1, is_amendment: r.amend, items: r.items, sections: [], desc: r.desc, row: r };
  }
  // The hive shows a balanced, organized slice: the most recent filings of each form, capped.
  function hiveRows(t) {
    var per = {}, out = [];
    SEC[t].filings.forEach(function (r) {
      if (out.length >= HIVE_MAX) return;
      var k = r.code;
      if ((per[k] = (per[k] || 0) + 1) <= HIVE_PER_FORM) out.push(r);
    });
    return out;
  }
  function realFilings(t) {
    var feed = {}, cur = false;
    if (LIVE[t]) liveFilings(t).forEach(function (f) { feed[f.accession] = f; });
    return hiveRows(t).map(function (r) {
      var f = feed[r.accession] || realFiling(t, r);
      f.real = true; f.row = r; f.iso = r.date;
      if (!f.desc) f.desc = r.desc;
      f.current = false;
      if (!cur && /^(10-K|10-Q|20-F|40-F)$/.test(r.code)) { f.current = true; cur = true; }
      return f;
    });
  }
  function filingByAccession(t, acc) {
    var hit = getFilings(t).filter(function (f) { return f.accession === acc; })[0];
    if (hit) return hit;
    var r = SEC[t] && SEC[t].filings.filter(function (x) { return x.accession === acc; })[0];
    return r ? realFiling(t, r) : null;
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
    if (isReal(t) && SEC[t] && SEC[t].status === 'ok') return (filingCache[t] = realFilings(t));
    if (TICKER_DB[t] && TICKER_DB[t].universe) return [];      // live list not loaded (yet)
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
    if (f.live || f.real) return liveDiffs(f);
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
  var searchInput = $('ticker-search'), resultsEl = $('search-results'), combo = $('search-combo');
  var results = [], resIdx = -1;

  // Every SEC-listed company (universe.json) plus the two fictional demo filers.
  function searchCompanies(q) {
    var Q = normTicker(q), U = q.trim().toUpperCase(), out = [], seen = {};
    function add(t, name, ex) { if (out.length < 8 && !seen[t]) { seen[t] = 1; out.push({ ticker: t, name: name, ex: ex }); } }
    if (!Q) return out;
    Object.keys(TICKER_DB).forEach(function (k) { var s = TICKER_DB[k]; if (s.fictional && (k.indexOf(Q) === 0 || s.name.toUpperCase().indexOf(U) >= 0)) add(k, s.name, 'Demo'); });
    if (UNIVERSE && UNIVERSE[Q]) add(Q, UNIVERSE[Q][1], UNIVERSE[Q][3]);
    var i, r;
    for (i = 0; i < universeRows.length && out.length < 8; i++) { r = universeRows[i]; if (r[0].indexOf(Q) === 0 && r[0].indexOf('-') < 0) add(r[0], r[1], r[3]); }
    if (U.length >= 2) {
      for (i = 0; i < universeRows.length && out.length < 8; i++) { r = universeRows[i]; if ((' ' + r[1].toUpperCase()).indexOf(' ' + U) >= 0) add(r[0], r[1], r[3]); }
      for (i = 0; i < universeRows.length && out.length < 8; i++) { r = universeRows[i]; if (r[1].toUpperCase().indexOf(U) >= 0) add(r[0], r[1], r[3]); }
    }
    if (!UNIVERSE) Object.keys(TICKER_DB).forEach(function (k) { if (k.indexOf(Q) === 0 || TICKER_DB[k].name.toUpperCase().indexOf(U) >= 0) add(k, TICKER_DB[k].name, TICKER_DB[k].exchange); });
    return out;
  }
  function renderResults() {
    if (!results.length) {
      if (searchInput.value.trim()) {
        resultsEl.innerHTML = '<li class="sr-none" role="option" aria-disabled="true">' + (UNIVERSE ? 'No SEC-listed company matches' : 'Loading the list of public companies\u2026') + '</li>';
        resultsEl.hidden = false; combo.setAttribute('aria-expanded', 'true');
      } else closeResults();
      return;
    }
    resultsEl.innerHTML = results.map(function (r, i) {
      var t = TICKER_DB[r.ticker] ? r.ticker : r.ticker, inList = pinned.indexOf(ensureKey(t)) >= 0;
      return '<li role="option" id="opt-' + esc(r.ticker) + '" data-t="' + esc(r.ticker) + '" aria-selected="' + (i === resIdx) + '">' +
        '<span class="sr-t">' + esc(r.ticker) + '</span><span class="sr-n">' + esc(r.name) + '</span>' +
        '<span class="sr-ex mono">' + esc(r.ex || '') + '</span>' +
        (inList ? '<span class="sr-in">Open</span>' : '<span class="sr-a">+ Open</span>') + '</li>';
    }).join('');
    resultsEl.hidden = false;
    combo.setAttribute('aria-expanded', 'true');
    searchInput.setAttribute('aria-activedescendant', resIdx >= 0 ? 'opt-' + results[resIdx].ticker : '');
  }
  function ensureKey(t) { return TICKER_DB[t] ? t : TICKER_DB[t.replace(/-/g, '')] ? t.replace(/-/g, '') : t; }
  function closeResults() { resultsEl.hidden = true; combo.setAttribute('aria-expanded', 'false'); searchInput.removeAttribute('aria-activedescendant'); resIdx = -1; }
  searchInput.addEventListener('focus', loadUniverse);
  searchInput.addEventListener('input', function () {
    var q = searchInput.value;
    results = searchCompanies(q);
    resIdx = results.length ? 0 : -1;
    renderResults();
    if (!UNIVERSE) loadUniverse().then(function () { if (searchInput.value === q) { results = searchCompanies(q); resIdx = results.length ? 0 : -1; renderResults(); } });
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
  function pick(t) { searchInput.value = ''; results = []; closeResults(); openTab(t); closeSidebarMobile(); }

  function sparkline(t, change) {
    var r = rng(hash(t + 'spark')), pts = [], v = 50;
    for (var i = 0; i < 24; i++) { v += (r() - 0.5) * 7; v = Math.max(20, Math.min(80, v)); pts.push(v); }
    pts[pts.length - 1] = pts[pts.length - 2] + (change >= 0 ? 10 : -10);
    var W = 240, H = 30, mn = Math.min.apply(null, pts), mx = Math.max.apply(null, pts);
    var d = pts.map(function (p, i) { return (i ? 'L' : 'M') + (i / (pts.length - 1) * W).toFixed(1) + ',' + (H - (p - mn) / (mx - mn + 0.01) * H).toFixed(1); }).join(' ');
    var c = change >= 0 ? '#6ee7b7' : '#ff8f8f';
    return '<svg class="sc-sparkline" viewBox="0 0 ' + W + ' ' + H + '" preserveAspectRatio="none" aria-hidden="true"><path d="' + d + '" fill="none" stroke="' + c + '" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" vector-effect="non-scaling-stroke"/></svg>';
  }
  // Real filing activity: filings per month over the last 12 months.
  function activityBars(t) {
    var s = SEC[t];
    if (!s || s.status !== 'ok') return '<div class="sc-activity-empty mono">' + (s && s.status === 'error' ? 'SEC unreachable' : 'loading from SEC\u2026') + '</div>';
    var now = new Date(), b = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0];
    s.filings.forEach(function (r) { var p = r.date.split('-'), m = (now.getFullYear() - +p[0]) * 12 + now.getMonth() - (+p[1] - 1); if (m >= 0 && m < 12) b[11 - m]++; });
    var mx = Math.max.apply(null, b) || 1;
    return '<svg class="sc-activity" viewBox="0 0 240 26" preserveAspectRatio="none" role="img" aria-label="Filings per month, last 12 months: ' + b.join(', ') + '">' +
      b.map(function (v, i) { var h = Math.max(1.5, v / mx * 24); return '<rect x="' + (i * 20 + 2) + '" y="' + (26 - h).toFixed(1) + '" width="16" height="' + h.toFixed(1) + '" rx="2"/>'; }).join('') + '</svg>';
  }
  function renderSidebar() {
    var box = $('sidebar-stocks');
    $('sidebar-empty').hidden = pinned.length > 0;
    box.innerHTML = pinned.map(function (t) {
      var s = TICKER_DB[t], sec = SEC[t], on = activeTab === t, mid;
      if (s.fictional) {
        var up = s.change >= 0;
        mid = '<div class="sc-mid"><span class="sc-price">$' + s.price.toFixed(2) + ' <span class="sc-change ' + (up ? 'up' : 'dn') + '">' + (up ? '+' : '') + s.change.toFixed(1) + '%</span></span><span class="sc-badge">' + getFilings(t).length + ' filings</span><span class="sc-badge">demo</span></div>' + sparkline(t, s.change);
      } else {
        var last = sec && sec.status === 'ok' && sec.filings[0];
        mid = '<div class="sc-mid"><span class="sc-badge">' + (sec && sec.status === 'ok' ? sec.filings.length.toLocaleString() + ' filings' : '\u2026') + '</span>' +
          (last ? '<span class="sc-badge">last ' + daysAgo(last.date) + 'd ago</span>' : '') +
          (sec && sec.status === 'ok' ? '<span class="sc-badge sc-live" title="Filing list read live from SEC EDGAR">SEC</span>' : '') +
          (LIVE[t] ? '<span class="sc-badge sc-deep" title="Deep-parsed by the ORACLE crawler: section text and changes">deep</span>' : '') + '</div>' + activityBars(t);
      }
      return '<div class="stock-card' + (on ? ' active' : '') + '" data-t="' + t + '">' +
        '<button type="button" class="sc-main" data-select="' + t + '" aria-pressed="' + on + '" aria-label="Open ' + esc(s.name) + ' tab">' +
        '<div class="sc-top"><span class="sc-ticker">' + t + '</span><span class="sc-ex mono">' + esc(s.fictional ? 'DEMO' : (s.exchange || '')) + '</span></div>' +
        '<div class="sc-name">' + esc(s.name) + '</div>' + mid + '</button>' +
        '<button type="button" class="sc-remove" data-remove="' + t + '" aria-label="Remove ' + t + ' from watchlist">' +
        '<svg viewBox="0 0 24 24" width="14" height="14" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg></button></div>';
    }).join('');  renderTabs();
  }
  $('sidebar-stocks').addEventListener('click', function (e) {
    var rm = e.target.closest('[data-remove]');
    if (rm) { removeStock(rm.getAttribute('data-remove')); return; }
    var sel = e.target.closest('[data-select]');
    if (sel) { openTab(sel.getAttribute('data-select')); closeSidebarMobile(); }
  });
  $('quick-add').innerHTML = ['NVDA', 'AAPL', 'TSM', 'JPM', 'XHLD'].map(function (t) { return '<button type="button" data-quick="' + t + '">' + t + '</button>'; }).join('');
  $('quick-add').addEventListener('click', function (e) { var b = e.target.closest('[data-quick]'); if (b) openTab(b.getAttribute('data-quick')); });

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
    opts = opts || {};
    t = ensureTicker(t);
    if (!t) return false;
    if (pinned.indexOf(t) >= 0) return true;
    pinned.push(t);
    reveal[t] = 0;
    save();
    renderSidebar();
    updateGraph();
    if (!opts.noSelect) selectStock(t);
    if (TICKER_DB[t].fictional) {
      reveal[t] = (opts.instant || reduceMotion) ? getFilings(t).length : 0;
      updateGraph();
      if (!opts.instant) runPipeline(t); else setIdleStatus();
      return true;
    }
    Promise.all([secLoad(t), liveLoad(t)]).then(function () {
      if (pinned.indexOf(t) < 0) return;
      delete filingCache[t];
      if (!(SEC[t] && SEC[t].status === 'ok')) {
        renderSidebar();
        if (TICKER_DB[t].universe) { consoleLine('k-warn', 'ERROR', t + ' \u00b7 SEC EDGAR unreachable (' + ((SEC[t] && SEC[t].error) || 'offline') + ')'); return; }
        reveal[t] = getFilings(t).length;   // featured company offline: illustrative fallback
        updateGraph();
        return;
      }
      startCrawl(t, opts.instant || reduceMotion);
    });
    return true;
  }

  function removeStock(t) {
    var i = pinned.indexOf(t);
    if (i < 0) return;
    pinned.splice(i, 1);
    delete reveal[t];
    if (CRAWL[t]) CRAWL[t].stop = true;
    save();
    if (openTabs.indexOf(t) >= 0) closeTab(t);
    if (activeFiling && activeFiling.ticker === t) closePanel();
    if (activeStock === t) activeStock = activeTab !== 'hive' ? activeTab : (pinned.length ? pinned[pinned.length - 1] : null);
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
    $('ws-context').textContent = 'Workspace \u00b7 ' + (activeTab === 'hive' ? 'Hive' : t);
    setMode(mode);
  }

  function updateTopbar() {
    var ctx = $('tb-context'), link = $('tb-edgar-link');
    if (!activeStock || activeTab === 'hive') {
      ctx.innerHTML = pinned.length ? '<b>Hive</b><span class="sep">\u00b7</span><span class="co">' + pinned.length + ' compan' + (pinned.length === 1 ? 'y' : 'ies') + '</span><span class="sep">\u00b7</span><span class="co">drag to rotate</span>'
        : '<span class="tb-hint">Search any public company to start</span>';
      link.href = 'https://www.sec.gov/edgar/search/';
      return;
    }
    var s = TICKER_DB[activeStock], sec = SEC[activeStock];
    ctx.innerHTML = '<b>' + activeStock + '</b><span class="sep">\u00b7</span><span class="co">' + esc(s.name) + '</span>' +
      (s.sector ? '<span class="sep">\u00b7</span><span class="co">' + esc(s.sector) + '</span>' : '') +
      '<span class="sep">\u00b7</span><span>' + (sec && sec.status === 'ok' ? sec.filings.length.toLocaleString() : getFilings(activeStock).length) + ' filings</span>';
    link.href = edgarUrl(activeStock, '') || 'https://www.sec.gov/edgar/search/';
  }

  /* =====================================================================
   * TABS: the hive overview plus one tab per company (each with its own chat)
   * ===================================================================== */
  var openTabs = [], activeTab = 'hive', threads = {}, TABS_KEY = 'edm_tabs_v1', legendWanted = false;   // the explorer opens from the list button; the globe gets the room
  function saveTabs() { store(TABS_KEY, { open: openTabs, active: activeTab }); }
  function renderTabs() {
    var hiveOn = activeTab === 'hive';
    $('view-tabs').innerHTML = '<div class="vt' + (hiveOn ? ' on' : '') + '"><button type="button" role="tab" id="vt-hive" aria-selected="' + hiveOn + '" tabindex="' + (hiveOn ? 0 : -1) + '" data-vt="hive">' +
      '<svg viewBox="0 0 24 24" width="14" height="14" aria-hidden="true"><circle cx="12" cy="12" r="8.5" stroke="currentColor" stroke-width="1.5" fill="none"/><ellipse cx="12" cy="12" rx="3.6" ry="8.5" stroke="currentColor" stroke-width="1.2" fill="none"/><path d="M3.5 12h17" stroke="currentColor" stroke-width="1.2"/></svg>Hive<small>' + pinned.length + '</small></button></div>' +
      openTabs.map(function (t) {
        var on = activeTab === t, s = TICKER_DB[t] || { name: t };
        return '<div class="vt' + (on ? ' on' : '') + '"><button type="button" role="tab" id="vt-' + esc(t) + '" aria-selected="' + on + '" tabindex="' + (on ? 0 : -1) + '" data-vt="' + esc(t) + '" title="' + esc(s.name) + '">' +
          '<b>' + esc(t) + '</b><small>' + esc(String(s.name).split(/[ ,]/)[0]) + '</small></button>' +
          '<button type="button" class="vt-x" data-vt-close="' + esc(t) + '" aria-label="Close ' + esc(t) + ' tab"><svg viewBox="0 0 24 24" width="12" height="12" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg></button></div>';
      }).join('');
  }
  $('view-tabs').addEventListener('click', function (e) {
    var x = e.target.closest('[data-vt-close]');
    if (x) { closeTab(x.getAttribute('data-vt-close')); return; }
    var b = e.target.closest('[data-vt]');
    if (b) switchTab(b.getAttribute('data-vt'));
  });
  $('view-tabs').addEventListener('keydown', function (e) {
    var keys = ['hive'].concat(openTabs), i = keys.indexOf(activeTab);
    var j = e.key === 'ArrowRight' ? (i + 1) % keys.length : e.key === 'ArrowLeft' ? (i - 1 + keys.length) % keys.length : -1;
    if (j >= 0 && e.target.closest('[data-vt]')) { e.preventDefault(); switchTab(keys[j]); var nb = $('vt-' + keys[j]); if (nb) nb.focus(); }
  });
  function openTab(t) {
    t = ensureTicker(t);
    if (!t) return false;
    if (pinned.indexOf(t) < 0) addStock(t, { noSelect: true });
    if (openTabs.indexOf(t) < 0) openTabs.push(t);
    switchTab(t);
    return true;
  }
  function closeTab(t) {
    var i = openTabs.indexOf(t);
    if (i < 0) return;
    openTabs.splice(i, 1);
    delete threads[t];
    if (activeTab === t) { activeTab = null; switchTab(openTabs[i] || openTabs[i - 1] || 'hive'); }
    else { renderTabs(); saveTabs(); }
  }
  function switchTab(key) {
    if (busy) { busy.stop(); setBusy(null); }
    if (activeTab) threads[activeTab] = messages.innerHTML;
    activeTab = key;
    messages.innerHTML = threads[key] || '';
    thread.hidden = !messages.innerHTML;
    if (panel.classList.contains('open') && (key === 'hive' || (activeFiling && activeFiling.ticker !== key))) closePanel();
    if (key === 'hive') {
      $('filings').hidden = true;
      $('legend').hidden = !legendWanted;
      $('legend-btn').setAttribute('aria-expanded', String(legendWanted));
      unfocus();
    } else {
      $('legend').hidden = true;
      $('filings').hidden = false;
      $('legend-btn').setAttribute('aria-expanded', 'true');
      renderFilings(key, true);
      focusHub(key);
    }
    selectStock(key === 'hive' ? activeStock : key);
    renderTabs();
    saveTabs();
  }

  /* =====================================================================
   * FILINGS PANEL + LIVE CRAWLER
   * Every public filing of the company, newest first, straight from SEC EDGAR. The crawler
   * walks down the list (indexing each filing into the hive); filings the ORACLE backend has
   * deep-parsed get a "deep" badge and open with real section changes.
   * ===================================================================== */
  var CRAWL = {}, flCat = 'all', flQuery = '', FL_RENDER_MAX = 400;
  function rowLabel(r) { return r.code + (r.amend ? '/A' : ''); }
  function rowDesc(r) {
    if (r.items.length) return itemNames(r.items).join(' \u00b7 ');
    var fi = F.BY_CODE[r.code];
    var generic = !r.desc || /^(PRIMARY DOCUMENT|DOCUMENT|FORM\b|SCHEDULE\b|EDGAR\b|[A-Z0-9\- \/]{1,12}$)/i.test(r.desc) || r.desc.toUpperCase().indexOf(r.code.replace('Form ', '').toUpperCase()) === 0;
    var d = !generic ? titleCase(r.desc) : (fi ? fi.name : 'SEC filing ' + r.secForm);
    return d + (r.report && /^(10-K|10-Q|20-F|40-F|6-K)$/.test(r.code) ? ' \u00b7 period ' + r.report : '');
  }
  function feedAccessions(t) { var m = {}; if (LIVE[t]) LIVE[t].filings.forEach(function (x) { if (x.status === 'fetched') m[x.accession] = x; }); return m; }
  function flMatches(r) {
    if (flCat !== 'all' && r.cat !== flCat) return false;
    if (!flQuery) return true;
    var hay = (rowLabel(r) + ' ' + r.secForm + ' ' + r.date + ' ' + r.accession + ' ' + rowDesc(r)).toUpperCase();
    return flQuery.split(/\s+/).every(function (w) { return hay.indexOf(w) >= 0; });
  }
  function renderFilings(t, resetFilter) {
    if (activeTab !== t) return;
    var s = SEC[t], info = TICKER_DB[t], list = $('fl-list');
    if (resetFilter) { flCat = 'all'; flQuery = ''; $('fl-q').value = ''; list.scrollTop = 0; }
    $('fl-kicker').textContent = info.fictional ? 'FICTIONAL DEMO FILER' : 'CIK ' + pad10(info.cik) + ' \u00b7 ' + (info.exchange || (s && s.meta && s.meta.exchanges[0]) || 'SEC registrant');
    $('fl-name').textContent = (s && s.meta && s.meta.name) ? titleCase(s.meta.name) : info.name;
    $('fl-edgar').href = edgarUrl(t, '') || 'https://www.sec.gov/edgar/search/';
    if (info.fictional) {
      $('fl-meta').textContent = 'Illustrative company. Its filings live in the hive; real companies list their full SEC history here.';
      $('fl-cats').innerHTML = ''; list.innerHTML = ''; $('fl-more').hidden = true;
      setCrawlText(t, 'demo data', 1);
      return;
    }
    if (!s || s.status !== 'ok') {
      $('fl-meta').textContent = s && s.status === 'error' ? 'Could not reach SEC EDGAR (' + s.error + ').' : 'Requesting the filing history from data.sec.gov\u2026';
      $('fl-cats').innerHTML = ''; list.innerHTML = ''; $('fl-more').hidden = true;
      setCrawlText(t, s && s.status === 'error' ? 'SEC unreachable' : 'GET data.sec.gov/submissions/CIK' + pad10(info.cik) + '.json', 0);
      return;
    }
    var m = s.meta;
    $('fl-meta').innerHTML = [m.sicDescription ? esc(titleCase(m.sicDescription)) : '', m.state ? 'Inc. ' + esc(m.state) : '', m.fiscalYearEnd ? 'FY ends ' + esc(MONTHS[+m.fiscalYearEnd.slice(0, 2) - 1] + ' ' + (+m.fiscalYearEnd.slice(2))) : '',
      '<b>' + s.filings.length.toLocaleString() + '</b> filings loaded' + (s.page < s.files.length ? ' (' + (s.files.length - s.page) + ' older batch' + (s.files.length - s.page === 1 ? '' : 'es') + ' on SEC)' : '')].filter(Boolean).join(' \u00b7 ');
    var counts = { all: s.filings.length };
    s.filings.forEach(function (r) { counts[r.cat] = (counts[r.cat] || 0) + 1; });
    $('fl-cats').innerHTML = ['all'].concat(CAT_ORDER.filter(function (c) { return counts[c]; })).map(function (c) {
      return '<button type="button" data-flcat="' + c + '" aria-pressed="' + (flCat === c) + '"' + (c !== 'all' ? ' style="--c:' + CATEGORIES[c].color + '"' : '') + '>' + (c === 'all' ? 'All' : esc(CATEGORIES[c].short)) + ' <span class="mono">' + counts[c].toLocaleString() + '</span></button>';
    }).join('');
    var deep = feedAccessions(t), cr = CRAWL[t] || { i: 0 }, shown = 0, html = [];
    for (var i = 0; i < s.filings.length && shown < FL_RENDER_MAX; i++) {
      var r = s.filings[i];
      if (!flMatches(r)) continue;
      shown++;
      var st = i < cr.i ? (deep[r.accession] ? 'parsed' : 'done') : i === cr.i && !cr.done ? 'active' : 'queued';
      html.push('<li class="fl-row st-' + st + '" data-i="' + i + '"><button type="button" data-acc="' + r.accession + '">' +
        '<span class="fl-st" aria-hidden="true"></span><span class="fl-date mono">' + r.date + '</span>' +
        '<span class="fl-form mono' + (r.tier ? ' t' + r.tier : '') + '" style="--c:' + CATEGORIES[r.cat].color + '">' + esc(rowLabel(r)) + '</span>' +
        '<span class="fl-desc">' + esc(rowDesc(r)) + '</span>' + (deep[r.accession] ? '<span class="fl-deep mono" title="Deep-parsed by ORACLE">deep</span>' : '') + '</button></li>');
    }
    var total = s.filings.filter(flMatches).length;
    list.innerHTML = html.join('') + (total > shown ? '<li class="fl-cap mono">Showing ' + shown + ' of ' + total.toLocaleString() + '. Narrow the filter to see the rest.</li>' : '') + (!total ? '<li class="fl-cap mono">No filings match.</li>' : '');
    $('fl-more').hidden = s.page >= s.files.length;
    $('fl-more').textContent = 'Load older filings (' + (s.files.length - s.page) + ' more batch' + (s.files.length - s.page === 1 ? '' : 'es') + ')';
    updateCrawlText(t);
  }
  function setCrawlText(t, text, frac) {
    if (activeTab !== t) return;
    $('fl-crawl-text').textContent = text;
    $('fl-bar').style.width = Math.round(Math.max(0, Math.min(1, frac)) * 100) + '%';
    $('fl-crawl').classList.toggle('busy', frac < 1);
  }
  function updateCrawlText(t) {
    var s = SEC[t], c = CRAWL[t];
    if (!s || s.status !== 'ok' || !c) return;
    var n = s.filings.length, deepN = Object.keys(feedAccessions(t)).length;
    if (c.done) setCrawlText(t, 'Indexed ' + n.toLocaleString() + ' filings from SEC EDGAR in ' + (s.ms < 1000 ? Math.max(1, s.ms) + ' ms' : (s.ms / 1000).toFixed(1) + 's') + (deepN ? ' \u00b7 ' + deepN + ' deep-parsed by ORACLE' : ''), 1);
    else setCrawlText(t, 'Crawling ' + t + ' \u00b7 ' + Math.min(c.i, n).toLocaleString() + ' / ' + n.toLocaleString() + (s.filings[c.i] ? ' \u00b7 ' + rowLabel(s.filings[c.i]) + ' ' + s.filings[c.i].date : ''), c.i / n);
  }
  function paintRows(t, from, to) {
    if (activeTab !== t) return;
    var deep = feedAccessions(t), c = CRAWL[t], list = $('fl-list');
    for (var i = from; i <= to; i++) {
      var li = list.querySelector('li[data-i="' + i + '"]');
      if (!li) continue;
      var r = SEC[t].filings[i], st = i < c.i ? (deep[r.accession] ? 'parsed' : 'done') : i === c.i && !c.done ? 'active' : 'queued';
      li.className = 'fl-row st-' + st;
      if (st === 'active' && !c.userScrolled) { var top = li.offsetTop - list.clientHeight * 0.35; if (Math.abs(list.scrollTop - top) > 4) list.scrollTop = top; }
    }
  }
  function startCrawl(t, instant) {
    var s = SEC[t], hive = hiveRows(t), hiveIdx = {}, deep = feedAccessions(t);
    hive.forEach(function (r) { hiveIdx[r.accession] = 1; });
    var c = CRAWL[t] = CRAWL[t] && CRAWL[t].i ? CRAWL[t] : { i: 0 };
    c.done = false; c.stop = false; c.userScrolled = false;
    var n = s.filings.length, token = ++pipeToken;
    pipeTicker = t;
    $('cc-title').textContent = 'oracle-crawler \u00b7 live SEC';
    if (instant) {
      c.i = n; c.done = true;
      reveal[t] = getFilings(t).length;
      updateGraph(); renderSidebar(); renderFilings(t); updateTopbar(); setIdleStatus();
      return;
    }
    stageEls.forEach(function (el) { el.classList.remove('active', 'done'); });
    stageEls[0].classList.add('active');
    autoOpenConsole();
    consoleLine('k-disc', 'DISCOVER', 'GET data.sec.gov/submissions/CIK' + pad10(TICKER_DB[t].cik) + '.json \u00b7 200 \u00b7 ' + n.toLocaleString() + ' filings \u00b7 ' + s.ms + ' ms');
    $('pipeline-status').textContent = t + ' \u00b7 ' + n.toLocaleString() + ' filings discovered on SEC EDGAR';
    renderSidebar(); renderFilings(t); updateTopbar();
    var step = Math.max(1, Math.ceil(n / 160)), shownHive = 0, deepSeen = 0;
    (function tick() {
      if (c.stop || pinned.indexOf(t) < 0) return;
      var from = c.i;
      c.i = Math.min(n, c.i + step);
      var newHive = 0;
      for (var i = from; i < c.i; i++) {
        var r = s.filings[i];
        if (hiveIdx[r.accession]) { newHive++; if (shownHive++ < 14 || deep[r.accession]) consoleLine(deep[r.accession] ? 'k-parse' : 'k-get', deep[r.accession] ? 'PARSED' : 'INDEX', t + ' ' + rowLabel(r) + ' ' + r.accession + ' \u00b7 ' + r.date + (deep[r.accession] ? ' \u00b7 sections + diff' : '')); }
        if (deep[r.accession]) deepSeen++;
      }
      if (token === pipeToken) {
        stageEls.forEach(function (el, k) { el.classList.toggle('done', k === 0 || (k === 1 && c.i >= n) || (k === 2 && deepSeen > 0 && c.i >= n)); el.classList.toggle('active', (k === 1 && c.i < n) || (k === 2 && deepSeen > 0 && c.i < n)); });
        $('pipeline-status').textContent = t + ' \u00b7 indexing ' + Math.min(c.i, n).toLocaleString() + ' / ' + n.toLocaleString() + ' filings' + (deepSeen ? ' \u00b7 ' + deepSeen + ' deep-parsed' : '');
      }
      if (newHive) { reveal[t] = Math.min(getFilings(t).length, (reveal[t] || 0) + newHive); updateGraph(); }
      paintRows(t, Math.max(0, from - 1), Math.min(n - 1, c.i));
      updateCrawlText(t);
      if (c.i < n) { setTimeout(tick, 40); return; }
      c.done = true;
      reveal[t] = getFilings(t).length;
      updateGraph(); paintRows(t, n - 1, n - 1); updateCrawlText(t); renderSidebar(); updateTopbar();
      consoleLine('k-cite', 'REPORT', t + ' \u00b7 ' + n.toLocaleString() + ' filings indexed \u00b7 ' + getFilings(t).length + ' in the hive' + (deepSeen ? ' \u00b7 ' + deepSeen + ' with section diffs' : ''));
      if (token === pipeToken) { stageEls.forEach(function (el) { el.classList.remove('active'); el.classList.add('done'); }); $('pipeline-status').textContent = t + ' \u00b7 crawl complete \u00b7 ' + n.toLocaleString() + ' filings'; setTimeout(function () { if (token === pipeToken) { stageEls.forEach(function (el) { el.classList.remove('done'); }); setIdleStatus(); } }, 3200); }
    })();
  }
  $('fl-list').addEventListener('click', function (e) {
    var b = e.target.closest('[data-acc]');
    if (!b || activeTab === 'hive') return;
    var f = filingByAccession(activeTab, b.getAttribute('data-acc'));
    if (f) openPanel(f, activeTab);
  });
  $('fl-list').addEventListener('wheel', function () { if (CRAWL[activeTab]) CRAWL[activeTab].userScrolled = true; }, { passive: true });
  $('fl-list').addEventListener('touchmove', function () { if (CRAWL[activeTab]) CRAWL[activeTab].userScrolled = true; }, { passive: true });
  $('fl-cats').addEventListener('click', function (e) { var b = e.target.closest('[data-flcat]'); if (!b) return; flCat = b.getAttribute('data-flcat'); renderFilings(activeTab); });
  var flT = 0;
  $('fl-q').addEventListener('input', function () { clearTimeout(flT); flT = setTimeout(function () { flQuery = $('fl-q').value.trim().toUpperCase(); renderFilings(activeTab); }, 120); });
  $('fl-more').addEventListener('click', function () {
    var t = activeTab, b = $('fl-more');
    b.disabled = true; b.textContent = 'Loading older filings\u2026';
    secLoadOlder(t).then(function (ok) {
      b.disabled = false;
      if (ok) { consoleLine('k-disc', 'DISCOVER', t + ' \u00b7 older batch loaded \u00b7 ' + SEC[t].filings.length.toLocaleString() + ' filings total'); delete filingCache[t]; if (CRAWL[t]) CRAWL[t].done = false; startCrawl(t, false); }
      renderFilings(t);
    }).catch(function () { b.disabled = false; b.textContent = 'Could not load older filings; try again'; });
  });

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
   * HIVE NETWORK: an organized 3D sphere (D3 joins the DOM, projection is ours)
   * Companies sit on a large sphere, grouped by sector. Each company's filings form a
   * small sphere around it, banded by category and ordered newest first. Drag (or the
   * arrow keys) rotates on both axes, the wheel zooms, and opening a stock tab flies the
   * camera to that company and spins its filing sphere in place.
   * ===================================================================== */
  var hasD3 = typeof window.d3 !== 'undefined';
  var svg, root, gGrid, gLinks, gShared, gPulses, gNodes, nodeMap = {}, gNodesData = [], gLinksData = [], sharedLinks = [], W = 800, H = 600;
  var tooltip = $('tooltip'), area = $('graph-area');
  var cam = { yaw: 0.6, pitch: -0.3, zoom: 0.6, ty: 0.6, tp: -0.3, tz: 1, pivot: [0, 0, 0], tpivot: [0, 0, 0], auto: true, focus: null, userZoom: false };
  var SPHERE_R = 0, CLUSTER_R = 120, FOCAL = 1400, pulses = [], dragMoved = false, rafId = 0, lastT = 0, autoTimer = 0;

  /* ---------- the outer shell: every SEC-listed company as a point ----------
   * Drawn on a canvas under the SVG (10,000+ points stay smooth). Points follow
   * universe.json order (exchange, then ticker) along the spiral, so exchanges form
   * bands and tickers run alphabetically. Hover shows the company; click opens its tab. */
  var shellCanvas = $('hive-shell'), shellCtx = shellCanvas && shellCanvas.getContext ? shellCanvas.getContext('2d') : null;
  var SHELL = null, shellHover = -1, DPR = Math.min(2, window.devicePixelRatio || 1);
  var EX_RGB = { NYSE: '150,163,230', Nasdaq: '120,190,210', CBOE: '200,180,140', TXSE: '200,160,190', OTC: '110,116,134' };
  function buildShell() {
    if (!universeRows.length || (SHELL && SHELL.n === universeRows.length)) return;
    var n = universeRows.length, pts = spiral(n), ranges = [], i;
    SHELL = { n: n, pos: new Float32Array(n * 3), sx: new Float32Array(n), sy: new Float32Array(n), d: new Float32Array(n), ranges: ranges, idx: {} };
    for (i = 0; i < n; i++) {
      SHELL.pos[i * 3] = pts[i][0]; SHELL.pos[i * 3 + 1] = pts[i][1]; SHELL.pos[i * 3 + 2] = pts[i][2];
      SHELL.idx[universeRows[i][0]] = i;
      var ex = universeRows[i][3] || '';
      if (!ranges.length || ranges[ranges.length - 1].ex !== ex) ranges.push({ ex: ex, a: i, b: i + 1 }); else ranges[ranges.length - 1].b = i + 1;
    }
    kick();
  }
  function shellR() { return Math.max(330, (SPHERE_R + CLUSTER_R) * 1.35); }
  function shellIndexOf(t) {
    if (!SHELL) return -1;
    var k = SHELL.idx[t]; if (k != null) return k;
    k = SHELL.idx[t.replace(/^(BRK)(B)$/, '$1-$2')]; return k != null ? k : -1;
  }
  function drawShell() {
    if (!shellCtx) return;
    var cw = Math.round(W * DPR), ch = Math.round(H * DPR);
    if (shellCanvas.width !== cw || shellCanvas.height !== ch) { shellCanvas.width = cw; shellCanvas.height = ch; }
    shellCtx.setTransform(DPR, 0, 0, DPR, 0, 0);
    shellCtx.clearRect(0, 0, W, H);
    if (!SHELL) return;
    var c = _ctx, P = SHELL.pos, Rs = shellR(), n = SHELL.n, i;
    var pv = c.pv, sk = Math.min(1.7, Math.sqrt(c.k)), dim = cam.focus ? 0.4 : 1;
    for (i = 0; i < n; i++) {
      var x = P[i * 3] * Rs - pv[0], y = P[i * 3 + 1] * Rs - pv[1], z = P[i * 3 + 2] * Rs - pv[2];
      var x1 = x * c.cyw + z * c.syw, z1 = -x * c.syw + z * c.cyw, y2 = y * c.cp - z1 * c.sp, z2 = y * c.sp + z1 * c.cp;
      var den = FOCAL - z2 * c.k;
      if (den < 160) { SHELL.d[i] = -1; continue; }
      var s = FOCAL / den;
      SHELL.sx[i] = c.cx + x1 * s * c.k; SHELL.sy[i] = c.cy + y2 * s * c.k;
      SHELL.d[i] = (z2 / Rs + 1) / 2;   // 0 = far side, 1 = facing you
    }
    // four depth bands per exchange keep fillStyle changes to a few dozen per frame
    SHELL.ranges.forEach(function (r) {
      var rgb = EX_RGB[r.ex] || '120,128,160';
      for (var band = 0; band < 4; band++) {
        var a = (0.08 + 0.55 * (band + 0.5) / 4) * dim, rad = (0.55 + 0.75 * (band + 0.5) / 4) * sk;
        shellCtx.fillStyle = 'rgba(' + rgb + ',' + a.toFixed(3) + ')';
        for (var j = r.a; j < r.b; j++) {
          var d = SHELL.d[j];
          if (d < 0 || (d >= 1 ? 3 : Math.floor(d * 4)) !== band) continue;
          shellCtx.fillRect(SHELL.sx[j] - rad, SHELL.sy[j] - rad, rad * 2, rad * 2);
        }
      }
    });
    // watchlisted companies: bright dot on the shell, wired to their filing sphere
    pinned.forEach(function (t) {
      var k = shellIndexOf(t), hub = nodeMap['hub:' + t];
      if (k < 0 || SHELL.d[k] < 0) return;
      var on = !cam.focus || cam.focus === t;
      if (hub && hub.sx != null && !hub.behind) {
        shellCtx.strokeStyle = 'rgba(103,232,249,' + ((on ? 0.38 : 0.12) * (0.4 + 0.6 * SHELL.d[k])).toFixed(3) + ')';
        shellCtx.lineWidth = 1;
        shellCtx.setLineDash([3, 5]);
        shellCtx.beginPath(); shellCtx.moveTo(SHELL.sx[k], SHELL.sy[k]); shellCtx.lineTo(hub.sx, hub.sy); shellCtx.stroke();
        shellCtx.setLineDash([]);
      }
      shellCtx.fillStyle = 'rgba(238,241,255,' + ((on ? 0.95 : 0.4) * (0.35 + 0.65 * SHELL.d[k])).toFixed(3) + ')';
      shellCtx.beginPath(); shellCtx.arc(SHELL.sx[k], SHELL.sy[k], 2.6 * sk, 0, Math.PI * 2); shellCtx.fill();
    });
    if (shellHover >= 0 && SHELL.d[shellHover] >= 0) {
      shellCtx.strokeStyle = 'rgba(238,241,255,0.95)'; shellCtx.lineWidth = 1.5;
      shellCtx.beginPath(); shellCtx.arc(SHELL.sx[shellHover], SHELL.sy[shellHover], 6, 0, Math.PI * 2); shellCtx.stroke();
    }
  }
  function shellPick(clientX, clientY) {
    if (!SHELL) return -1;
    var r = area.getBoundingClientRect(), x = clientX - r.left, y = clientY - r.top, best = -1, bd = 64;
    for (var i = 0; i < SHELL.n; i++) {
      if (SHELL.d[i] < 0.5) continue;   // only the side facing you
      var dx = SHELL.sx[i] - x, dy = SHELL.sy[i] - y, dd = dx * dx + dy * dy;
      if (dd < bd) { bd = dd; best = i; }
    }
    return best;
  }
  function shellTip(i, ev) {
    var u = universeRows[i];
    tooltip.innerHTML = '<b>' + esc(u[0]) + '</b> \u00b7 ' + esc(titleCase(u[1])) + '<br>' + esc(u[3] || 'Unlisted') + ' \u00b7 CIK ' + u[2] + '<br><span style="color:#949db2">Click to open its live SEC filings</span>';
    tooltip.classList.add('visible');
    moveTip(ev);
  }

  function nodeR(d) {
    if (d.kind === 'hub') return 22;
    if (d.kind === 'cat') return 4;
    if (d.kind === 'entity') return 8;
    return d.tier === 1 ? 8.5 : d.tier === 2 ? 6.5 : 5;
  }
  function clampP(p) { return Math.max(-1.4, Math.min(1.4, p)); }
  function angDiff(a, b) { var d = (a - b) % (2 * Math.PI); if (d > Math.PI) d -= 2 * Math.PI; if (d < -Math.PI) d += 2 * Math.PI; return d; }
  // Points along a spherical spiral: neighbours in the list are neighbours on the sphere,
  // so sorted input (by sector, by category) lands in tidy bands.
  function spiral(n) {
    var pts = [], phi = 0;
    if (n === 1) return [[0, 0, 1]];
    for (var i = 0; i < n; i++) {
      var h = -1 + 2 * i / (n - 1), th = Math.acos(h);
      phi = (i === 0 || i === n - 1) ? 0 : (phi + 3.6 / Math.sqrt(n * (1 - h * h))) % (2 * Math.PI);
      pts.push([Math.sin(th) * Math.cos(phi), h, Math.sin(th) * Math.sin(phi)]);
    }
    return pts;
  }

  function initGraph() {
    if (!hasD3) {
      $('graph-empty').querySelector('h1').textContent = 'Network view unavailable.';
      $('graph-empty').querySelector('p').textContent = 'The D3 library could not load (offline or blocked). The watchlist, filings, analysis panel and workspace still work.';
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
    gGrid = root.append('g').attr('class', 'sphere-grid');
    gLinks = root.append('g');
    gShared = root.append('g');
    gPulses = root.append('g');
    gNodes = root.append('g');
    measure();

    var drag = null, el = svg.node();
    el.addEventListener('pointerdown', function (e) {
      if (e.button !== 0) return;
      drag = { x: e.clientX, y: e.clientY, id: e.pointerId, moved: 0 };
      dragMoved = false;
    });
    window.addEventListener('pointermove', function (e) {
      if (!drag || e.pointerId !== drag.id) return;
      var dx = e.clientX - drag.x, dy = e.clientY - drag.y;
      drag.x = e.clientX; drag.y = e.clientY; drag.moved += Math.abs(dx) + Math.abs(dy);
      if (!dragMoved && drag.moved > 6) { dragMoved = true; area.classList.add('rotating'); hideTip(); }
      if (!dragMoved) return;
      cam.yaw = cam.ty = cam.ty + dx * 0.0065;
      cam.pitch = cam.tp = clampP(cam.tp + dy * 0.0065);
      pauseAuto();
      kick();
    });
    el.addEventListener('pointermove', function (e) {
      if (drag || !SHELL) return;
      var onNode = e.target.closest && e.target.closest('g.node');
      var k = onNode ? -1 : shellPick(e.clientX, e.clientY);
      if (k !== shellHover) { shellHover = k; area.classList.toggle('over-shell', k >= 0); kick(); }
      if (k >= 0) shellTip(k, e); else if (!onNode) hideTip();
    });
    el.addEventListener('pointerleave', function () { if (shellHover >= 0) { shellHover = -1; area.classList.remove('over-shell'); hideTip(); kick(); } });
    el.addEventListener('click', function (e) {
      if (dragMoved || (e.target.closest && e.target.closest('g.node'))) return;
      var k = shellHover >= 0 ? shellHover : shellPick(e.clientX, e.clientY);
      if (k >= 0) { hideTip(); shellHover = -1; area.classList.remove('over-shell'); openTab(universeRows[k][0]); }
    });
    function up(e) { if (drag && e.pointerId === drag.id) { drag = null; area.classList.remove('rotating'); setTimeout(function () { dragMoved = false; }, 0); } }
    window.addEventListener('pointerup', up);
    window.addEventListener('pointercancel', up);
    el.addEventListener('wheel', function (e) {
      e.preventDefault();
      cam.tz = Math.max(0.25, Math.min(6, cam.tz * Math.exp(-e.deltaY * 0.0015)));
      cam.userZoom = true; pauseAuto(); kick();
    }, { passive: false });
    area.addEventListener('keydown', function (e) {
      if (e.target !== area && e.target !== el) return;
      var k = { ArrowLeft: [-0.12, 0], ArrowRight: [0.12, 0], ArrowUp: [0, -0.12], ArrowDown: [0, 0.12] }[e.key];
      if (k) { e.preventDefault(); cam.ty += k[0]; cam.tp = clampP(cam.tp + k[1]); pauseAuto(); kick(); }
      else if (e.key === '+' || e.key === '=') { cam.tz = Math.min(6, cam.tz * 1.2); cam.userZoom = true; kick(); }
      else if (e.key === '-') { cam.tz = Math.max(0.25, cam.tz / 1.2); cam.userZoom = true; kick(); }
    });
    if (window.ResizeObserver) new ResizeObserver(function () { measure(); if (!cam.userZoom) cam.tz = targetZoom(); kick(); }).observe(area);
    document.addEventListener('visibilitychange', kick);
    if (!reduceMotion) setInterval(pulse, 900);
    renderLegend();
    kick();
  }
  function measure() { W = area.clientWidth || 800; H = area.clientHeight || 600; }
  // .main and the graph clip their children; never let focus() scroll them sideways.
  ['main', 'graph-area'].forEach(function (id) { var el = $(id); el.addEventListener('scroll', function () { if (el.scrollLeft || el.scrollTop) { el.scrollLeft = 0; el.scrollTop = 0; } }); });
  function pauseAuto() {
    cam.auto = false;
    clearTimeout(autoTimer);
    autoTimer = setTimeout(function () { if (!cam.focus && !reduceMotion) { cam.auto = true; kick(); } }, 7000);
  }
  // The part of the graph not covered by the filings panel / explorer (left or bottom) or the analysis panel.
  function viewBox() {
    var left = 0, right = 0, bottom = 0, ov = activeTab !== 'hive' ? $('filings') : $('legend');
    if (ov && !ov.hidden && ov.offsetWidth) {
      if (ov.offsetHeight > H * 0.7 && ov.offsetWidth < W * 0.6) left = ov.offsetWidth + 16;
      else if (ov.offsetWidth >= W * 0.6) bottom = ov.offsetHeight + 12;
    }
    if (panel && panel.classList.contains('open') && panel.offsetWidth < W * 0.7) right = panel.offsetWidth;
    var w = Math.max(200, W - left - right), h = Math.max(160, H - bottom);
    return { x: left + w / 2, y: h / 2, w: w, h: h };
  }
  function sceneR() { return SHELL ? shellR() : SPHERE_R + CLUSTER_R; }
  function targetZoom() {
    var v = viewBox(), r = cam.focus ? (nodeMap['hub:' + cam.focus] ? nodeMap['hub:' + cam.focus].rc : CLUSTER_R) * 1.15 : sceneR() + 30;
    return Math.max(0.25, Math.min(4, Math.min(v.w, v.h) * 0.44 / Math.max(60, r)));
  }

  function hubOrder() {
    function key(t) { var s = TICKER_DB[t] || {}; return (s.fictional ? 'zz' : '') + (s.sector || 'zy'); }
    return pinned.slice().sort(function (a, b) { var ka = key(a), kb = key(b); return ka < kb ? -1 : ka > kb ? 1 : pinned.indexOf(a) - pinned.indexOf(b); });
  }
  function clusterR(m, solo) { return solo ? 120 + 9 * Math.sqrt(m) : 52 + 8.5 * Math.sqrt(m); }

  function buildData() {
    var nodes = [], links = [], keep = {}, hubs = hubOrder(), n = hubs.length, dirs = spiral(Math.max(n, 1)), rcMax = 60;
    hubs.forEach(function (t) { rcMax = Math.max(rcMax, clusterR(getFilings(t).slice(0, reveal[t] || 0).filter(visibleFiling).length, n === 1)); });
    // big enough that neighbouring company spheres never overlap
    var R = n > 1 ? Math.max(rcMax * 1.45, rcMax * 2.3 / Math.sqrt(4 * Math.PI / n)) : 0, maxC = 60;
    SPHERE_R = R;
    function node(id, props, start) {
      var nd = nodeMap[id];
      if (!nd) { nd = { id: id, p: (start || props.t).slice(), sx: 0, sy: 0, s: 1, z: 0, depth: 1 }; nd.isNew = true; nodeMap[id] = nd; }
      for (var k in props) nd[k] = props[k];
      keep[id] = 1;
      nodes.push(nd);
      return nd;
    }
    hubs.forEach(function (t, i) {
      var c = [dirs[i][0] * R, dirs[i][1] * R, dirs[i][2] * R];
      var hub = node('hub:' + t, { kind: 'hub', ticker: t, label: t, t: c }, [c[0] * 0.2, c[1] * 0.2, c[2] * 0.2]);
      var fl = getFilings(t).slice(0, reveal[t] || 0).filter(visibleFiling);
      var ordered = fl.map(function (f, k) { return { f: f, k: k }; }).sort(function (a, b) { return (CAT_ORDER.indexOf(a.f.cat) - CAT_ORDER.indexOf(b.f.cat)) || (a.k - b.k); }).map(function (x) { return x.f; });
      var m = ordered.length, rc = clusterR(m, n === 1), pts = spiral(Math.max(m, 1)), bands = {};
      hub.rc = rc; maxC = Math.max(maxC, rc);
      ordered.forEach(function (f, k) {
        var u = pts[k];
        f._u = u;
        (bands[f.cat] = bands[f.cat] || []).push(f);
      });
      Object.keys(bands).forEach(function (cat) {
        var sx = 0, sy = 0, sz = 0;
        bands[cat].forEach(function (f) { sx += f._u[0]; sy += f._u[1]; sz += f._u[2]; });
        var L = Math.sqrt(sx * sx + sy * sy + sz * sz) || 1;
        var cn = node('cat:' + t + ':' + cat, { kind: 'cat', ticker: t, cat: cat, t: [c[0] + sx / L * rc * 0.5, c[1] + sy / L * rc * 0.5, c[2] + sz / L * rc * 0.5] }, hub.p);
        links.push({ id: 'hc:' + t + ':' + cat, source: hub, target: cn, kind: 'hc', cat: cat });
        bands[cat].forEach(function (f) {
          var fn = node('f:' + t + ':' + f.id, { kind: 'filing', ticker: t, cat: cat, filing: f, tier: tierOf(f.form), t: [c[0] + f._u[0] * rc, c[1] + f._u[1] * rc, c[2] + f._u[2] * rc] }, cn.p);
          links.push({ id: 'cf:' + t + ':' + f.id, source: cn, target: fn, kind: 'cf', cat: cat });
        });
      });
    });
    CLUSTER_R = maxC;
    sharedLinks = [];
    SHARED_ENTITIES.forEach(function (e) {
      var ts = (e.tickers === '*' ? pinned.filter(function (t) { return !TICKER_DB[t].universe && !TICKER_DB[t].fictional; }) : e.tickers.filter(function (t) { return pinned.indexOf(t) >= 0; }));
      if (ts.length < 2) return;
      var sx = 0, sy = 0, sz = 0;
      ts.forEach(function (t) { var h = nodeMap['hub:' + t]; sx += h.t[0]; sy += h.t[1]; sz += h.t[2]; });
      var L = Math.sqrt(sx * sx + sy * sy + sz * sz), j = (hash(e.key) % 100) / 100;
      var dir = L > 1 ? [sx / L, sy / L, sz / L] : [Math.cos(j * 6.28), j - 0.5, Math.sin(j * 6.28)];
      var en = node('e:' + e.key, { kind: 'entity', etype: e.type, label: e.label, note: e.note, tickers: ts, t: [dir[0] * R * 0.42, dir[1] * R * 0.42, dir[2] * R * 0.42] }, [0, 0, 0]);
      ts.forEach(function (t) {
        var l = { id: 'sh:' + e.key + ':' + t, source: en, target: nodeMap['hub:' + t], kind: 'shared', etype: e.type };
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
      function (en) { return en.append('line').attr('stroke', function (d) { return d.kind === 'hc' ? 'rgba(168,180,255,0.5)' : CATEGORIES[d.cat].color; })
        .attr('stroke-width', function (d) { return d.kind === 'hc' ? 1.1 : 0.7; }); },
      function (up) { return up; },
      function (ex) { return ex.remove(); });
    gShared.selectAll('line').data(shared, function (d) { return d.id; }).join(
      function (en) { return en.append('line').attr('class', 'shared').attr('stroke', function (d) { return ENTITY_TYPES[d.etype].color; })
        .attr('stroke-width', 1).attr('stroke-dasharray', '2 6').attr('stroke-linecap', 'round'); },
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
        g.append('text').text(d.label).attr('text-anchor', 'middle').attr('dy', '0.35em').attr('font-size', d.label.length > 4 ? 9 : 11).attr('font-weight', 600).attr('fill', '#eef1f8').attr('font-family', 'Geist Mono, monospace');
        g.append('circle').attr('class', 'focus-ring').attr('r', 27);
      } else if (d.kind === 'cat') {
        g.append('circle').attr('r', 4).attr('fill', CATEGORIES[d.cat].color).attr('opacity', 0.9);
      } else if (d.kind === 'entity') {
        g.append('path').attr('d', 'M0,-8L8,0L0,8L-8,0Z').attr('fill', ENTITY_TYPES[d.etype].color).attr('fill-opacity', 0.85).attr('filter', 'url(#soft-glow)');
        g.append('circle').attr('class', 'focus-ring').attr('r', 12);
      } else {
        var c = CATEGORIES[d.cat].color;
        if (d.tier === 1) g.append('circle').attr('r', 12).attr('fill', 'none').attr('stroke', '#f5c97a').attr('stroke-opacity', 0.85).attr('stroke-width', 1.2);
        else if (d.tier === 2) g.append('circle').attr('r', 9).attr('fill', 'none').attr('stroke', c).attr('stroke-opacity', 0.55).attr('stroke-width', 0.9);
        if (d.filing.live) g.append('circle').attr('r', 15).attr('fill', 'none').attr('stroke', '#67e8f9').attr('stroke-opacity', 0.7).attr('stroke-width', 1).attr('stroke-dasharray', '2 3');
        g.append('circle').attr('class', 'core').attr('r', nodeR(d)).attr('fill', c).attr('fill-opacity', d.tier === 1 ? 0.95 : d.tier === 2 ? 0.85 : 0.65);
        if (d.tier === 1) g.append('text').text(d.filing.form.replace('Form ', 'F')).attr('text-anchor', 'middle').attr('dy', 23).attr('font-size', 8.5).attr('fill', '#98a2c4');
        g.append('circle').attr('class', 'focus-ring').attr('r', d.tier === 1 ? 16 : 11);
      }
    });
    en.filter(function (d) { return d.kind !== 'cat'; })
      .attr('tabindex', 0).attr('role', 'button')
      .attr('aria-label', function (d) { return ariaFor(d); })
      .on('click', function (ev, d) { if (dragMoved) return; activate(d); })
      .on('keydown', function (ev, d) { if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); activate(d); } })
      .on('mouseenter focus', function (ev, d) { if (!dragMoved) showTip(ev, d); })
      .on('mousemove', function (ev) { moveTip(ev); })
      .on('mouseleave blur', hideTip);
    if (!reduceMotion) inner.attr('transform', 'scale(0.01)').transition().duration(700).ease(d3.easeCubicOut).attr('transform', 'scale(1)');
    gNodesData.forEach(function (n) { n.isNew = false; });
    if (cam.focus && nodeMap['hub:' + cam.focus]) aimAt(cam.focus);
    else if (!cam.userZoom) cam.tz = targetZoom();
    if (activeStock) highlightCluster(activeStock);
    applyHighlight();
    updateExplorer();
    kick();
  }

  /* ---------- camera ---------- */
  function aimAt(t) {
    var h = nodeMap['hub:' + t];
    if (!h) return;
    var x = h.t[0], y = h.t[1], z = h.t[2];
    if (SPHERE_R > 0) {
      var yaw = Math.atan2(-x, z), rxz = Math.sqrt(x * x + z * z);
      cam.ty = cam.yaw + angDiff(yaw, cam.yaw);
      cam.tp = clampP(Math.atan2(y, rxz));
    }
    cam.tpivot = h.t.slice();
    if (!cam.userZoom) cam.tz = targetZoom();
  }
  function focusHub(t) {
    cam.focus = t; cam.auto = false; cam.userZoom = false;
    clearTimeout(autoTimer);
    aimAt(t);
    kick();
  }
  function unfocus() {
    cam.focus = null; cam.userZoom = false; cam.tpivot = [0, 0, 0];
    cam.auto = !reduceMotion;
    cam.tz = targetZoom();
    kick();
  }
  function fit() { cam.userZoom = false; if (cam.focus) aimAt(cam.focus); else { cam.tpivot = [0, 0, 0]; cam.tz = targetZoom(); cam.auto = !reduceMotion; } kick(); }

  /* ---------- render loop ---------- */
  function kick() { if (!rafId && hasD3 && root) rafId = requestAnimationFrame(frame); }
  function frame(ts) {
    rafId = 0;
    if (document.hidden) { lastT = 0; return; }
    var dt = lastT ? Math.min(60, ts - lastT) : 16, moving = false;
    lastT = ts;
    if (cam.auto && !reduceMotion) { cam.ty += 0.00011 * dt; cam.tp = clampP(-0.28 + Math.sin(ts / 7000) * 0.32); moving = true; }
    else if (cam.focus && !reduceMotion && !area.classList.contains('rotating')) { cam.ty += 0.00004 * dt; moving = true; }
    var e = reduceMotion ? 1 : 1 - Math.pow(0.9, dt / 16), d;
    d = angDiff(cam.ty, cam.yaw); cam.yaw += d * e; if (Math.abs(d) > 1e-4) moving = true;
    d = cam.tp - cam.pitch; cam.pitch += d * e; if (Math.abs(d) > 1e-4) moving = true;
    d = cam.tz - cam.zoom; cam.zoom += d * e; if (Math.abs(d) > 1e-4) moving = true;
    for (var k = 0; k < 3; k++) { d = cam.tpivot[k] - cam.pivot[k]; cam.pivot[k] += d * e; if (Math.abs(d) > 0.05) moving = true; }
    var ne = reduceMotion ? 1 : 1 - Math.pow(0.86, dt / 16);
    for (var i = 0; i < gNodesData.length; i++) {
      var n = gNodesData[i];
      for (k = 0; k < 3; k++) { d = n.t[k] - n.p[k]; if (Math.abs(d) > 0.05) { n.p[k] += d * ne; moving = true; } else n.p[k] = n.t[k]; }
    }
    render(ts);
    if (pulses.length) moving = true;
    if (moving) kick(); else lastT = 0;
  }
  var _ctx = {};
  function setupProjection() {
    var v = viewBox();
    _ctx = { cx: v.x, cy: v.y, cyw: Math.cos(cam.yaw), syw: Math.sin(cam.yaw), cp: Math.cos(cam.pitch), sp: Math.sin(cam.pitch), k: cam.zoom, pv: cam.pivot, D: Math.max(80, sceneR()) };
  }
  function project(p, out) {
    var c = _ctx, x = p[0] - c.pv[0], y = p[1] - c.pv[1], z = p[2] - c.pv[2];
    var x1 = x * c.cyw + z * c.syw, z1 = -x * c.syw + z * c.cyw;
    var y2 = y * c.cp - z1 * c.sp, z2 = y * c.sp + z1 * c.cp;
    var s = FOCAL / Math.max(120, FOCAL - z2 * c.k);
    out.sx = c.cx + x1 * s * c.k; out.sy = c.cy + y2 * s * c.k; out.s = s; out.z = z2;
    out.depth = Math.max(0, Math.min(1, (z2 + c.D) / (2 * c.D)));
    out.behind = FOCAL - z2 * c.k < 160;
    return out;
  }
  function render(ts) {
    if (!gNodes) return;
    setupProjection();
    var focus = cam.focus, sk = Math.sqrt(_ctx.k);
    gNodesData.forEach(function (n) { project(n.p, n); });
    drawShell();
    function nodeOpacity(d) {
      if (d.behind) return 0;
      var o = 0.22 + 0.78 * d.depth;
      if (focus && ((d.ticker && d.ticker !== focus) || (d.kind === 'entity' && d.tickers.indexOf(focus) < 0))) o *= 0.22;
      return o;
    }
    gNodes.selectAll('g.node')
      .attr('transform', function (d) { return 'translate(' + d.sx.toFixed(1) + ',' + d.sy.toFixed(1) + ') scale(' + Math.min(3, d.s * sk).toFixed(3) + ')'; })
      .attr('opacity', function (d) { return nodeOpacity(d).toFixed(3); })
      .sort(function (a, b) { return a.z - b.z; });
    function line(sel, base) {
      sel.attr('x1', function (d) { return d.source.sx; }).attr('y1', function (d) { return d.source.sy; })
        .attr('x2', function (d) { return d.target.sx; }).attr('y2', function (d) { return d.target.sy; })
        .attr('opacity', function (d) { return (Math.min(nodeOpacity(d.source), nodeOpacity(d.target)) * (typeof base === 'function' ? base(d) : base)).toFixed(3); });
    }
    line(gLinks.selectAll('line'), function (d) { return d.kind === 'hc' ? 0.9 : 0.4; });
    line(gShared.selectAll('line'), 0.75);
    renderGrid();
    var now = ts || performance.now();
    pulses = pulses.filter(function (p) { return now - p.t0 < p.dur && p.l.source.sx != null; });
    gPulses.selectAll('circle').data(pulses, function (p) { return p.id; }).join(
      function (en) { return en.append('circle').attr('r', 2.6).attr('filter', 'url(#soft-glow)').attr('fill', function (p) { return p.color; }); },
      function (up) { return up; }, function (ex) { return ex.remove(); })
      .attr('cx', function (p) { var u = (now - p.t0) / p.dur, a = p.flip ? p.l.target : p.l.source, b = p.flip ? p.l.source : p.l.target; return a.sx + (b.sx - a.sx) * u; })
      .attr('cy', function (p) { var u = (now - p.t0) / p.dur, a = p.flip ? p.l.target : p.l.source, b = p.flip ? p.l.source : p.l.target; return a.sy + (b.sy - a.sy) * u; })
      .attr('opacity', function (p) { return (0.95 - 0.7 * (now - p.t0) / p.dur) * Math.min(nodeOpacity(p.l.source), nodeOpacity(p.l.target)); });
  }
  // Faint latitude / longitude rings make the sphere legible while it turns.
  function renderGrid() {
    var R = SHELL ? shellR() : SPHERE_R > 0 ? SPHERE_R : (pinned.length ? CLUSTER_R * 1.25 : 0), paths = [], tmp = {};
    if (R > 0) {
      var c = cam.focus && nodeMap['hub:' + cam.focus] ? nodeMap['hub:' + cam.focus] : null;
      var center = SHELL || SPHERE_R > 0 ? [0, 0, 0] : (c ? c.t : [0, 0, 0]);
      var lat, lon, i, d;
      for (lat = -60; lat <= 60; lat += 30) {
        d = ''; var cl = Math.cos(lat * Math.PI / 180), sl = Math.sin(lat * Math.PI / 180);
        for (i = 0; i <= 48; i++) { var a = i / 48 * 2 * Math.PI; project([center[0] + R * cl * Math.cos(a), center[1] + R * sl, center[2] + R * cl * Math.sin(a)], tmp); d += (i ? 'L' : 'M') + tmp.sx.toFixed(1) + ',' + tmp.sy.toFixed(1); }
        paths.push({ id: 'lat' + lat, d: d });
      }
      for (lon = 0; lon < 180; lon += 30) {
        d = ''; var co = Math.cos(lon * Math.PI / 180), so = Math.sin(lon * Math.PI / 180);
        for (i = 0; i <= 48; i++) { var b = i / 48 * 2 * Math.PI; project([center[0] + R * Math.cos(b) * co, center[1] + R * Math.sin(b), center[2] + R * Math.cos(b) * so], tmp); d += (i ? 'L' : 'M') + tmp.sx.toFixed(1) + ',' + tmp.sy.toFixed(1); }
        paths.push({ id: 'lon' + lon, d: d });
      }
    }
    gGrid.selectAll('path').data(paths, function (p) { return p.id; }).join('path').attr('d', function (p) { return p.d; });
  }

  function pulse() {
    if (document.hidden || !sharedLinks.length) return;
    var l = sharedLinks[Math.floor(Math.random() * sharedLinks.length)];
    pulses.push({ id: Math.random().toString(36).slice(2), l: l, t0: performance.now(), dur: 1800, flip: Math.random() < 0.5, color: ENTITY_TYPES[l.etype].color });
    kick();
  }

  function highlightCluster(t) {
    if (!hasD3 || !gNodes) return;
    gNodes.selectAll('g.n-hub').select('circle:nth-child(2)').attr('stroke-width', function (d) { return d.ticker === t ? 2.6 : 1.6; }).attr('stroke', function (d) { return d.ticker === t ? '#eef0ff' : '#c9ceff'; });
  }

  function ariaFor(d) {
    if (d.kind === 'hub') return d.ticker + ', ' + TICKER_DB[d.ticker].name + '. Press Enter to open its tab.';
    if (d.kind === 'entity') return ENTITY_TYPES[d.etype].label + ': ' + d.label + ', links ' + d.tickers.join(', ');
    return d.ticker + ' ' + d.filing.id + ', ' + CATEGORIES[d.cat].label + ', filed ' + d.filing.date + ', materiality ' + Math.round(d.filing.materiality * 100) + '. Press Enter to analyze.';
  }
  function activate(d) {
    if (d.kind === 'hub') { openTab(d.ticker); return; }
    if (d.kind === 'entity') { explainEntity(d); return; }
    if (d.kind === 'filing') { if (activeTab !== d.ticker) openTab(d.ticker); openPanel(d.filing, d.ticker); }
  }
  function showTip(ev, d) {
    var html;
    if (d.kind === 'hub') { var s = TICKER_DB[d.ticker], sc = SEC[d.ticker]; html = '<b>' + d.ticker + '</b> \u00b7 ' + esc(s.name) + '<br>' + (sc && sc.status === 'ok' ? sc.filings.length.toLocaleString() + ' SEC filings' : getFilings(d.ticker).length + ' filings') + (s.sector ? ' \u00b7 ' + esc(s.sector) : '') + '<br><span style="color:#949db2">Click to open its tab</span>'; }
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
    if (activeTab !== 'hive') {
      var fl = $('filings'), open = show === undefined ? fl.hidden : show;
      fl.hidden = !open; $('legend-btn').setAttribute('aria-expanded', String(open));
      if (!cam.userZoom) cam.tz = targetZoom();
      kick();
      return;
    }
    var lg = $('legend'), b = $('legend-btn');
    if (show === undefined) show = lg.hidden;
    lg.hidden = !show;
    legendWanted = show;
    b.setAttribute('aria-expanded', String(show));
    if (!cam.userZoom) cam.tz = targetZoom();
    kick();
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
    $('panel-sub').textContent = (f.form + (f.is_amendment ? '/A' : '')) + ' \u00b7 ' + formInfo(f.form).name + ' \u00b7 Filed ' + f.date + (tierOf(f.form) ? ' \u00b7 Tier ' + tierOf(f.form) : '');
    panel.classList.add('open');
    panel.setAttribute('aria-hidden', 'false');
    if (!cam.userZoom) cam.tz = targetZoom();
    kick();
    $('ws-context').textContent = 'Workspace \u00b7 ' + t + ' \u00b7 ' + f.id;
    if (f.real && !f.live) setTimeout(kick, 0);
    diffFilter = 'all';
    setTab('crawler');
    setTimeout(function () { try { $('panel-close').focus({ preventScroll: true }); } catch (e) { $('panel-close').focus(); } }, 50);
  }
  function closePanel() {
    panelToken++;
    panel.classList.remove('open');
    panel.setAttribute('aria-hidden', 'true');
    activeFiling = null;
    if (!cam.userZoom) cam.tz = targetZoom();
    kick();
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
    if (f.real && !f.live) {   // listed live from SEC, not deep-parsed yet: say exactly that
      var row = f.row || {};
      stages[0].lines = [
        ['l-info', '> GET data.sec.gov/submissions/CIK' + pad10(cik) + '.json (live, from your browser)'],
        ['l-ok', '> Resolved ' + t + ' \u2192 ' + info.name],
        ['l-ok', '> Accession ' + f.accession + ' \u00b7 ' + f.form + (f.is_amendment ? '/A' : '') + ' \u00b7 ' + fi.name],
        f.is_amendment ? ['l-warn', '> Amendment: supersedes an earlier ' + f.form] : ['l-mut', '  original filing']];
      stages[1].lines = [
        ['l-info', '> Primary document: ' + (row.doc || 'see filing index') + (row.size ? ' \u00b7 ' + fmtKB(row.size) + ' on SEC' : '')],
        ['l-mut', '  not downloaded yet: the ORACLE backend fetches it at \u226410 req/s and hashes it (SHA-256)']];
      stages[2].lines = [['l-mut', '  queued for the ORACLE extractor: sections, tables, iXBRL facts']];
      stages[3].lines = (f.items && f.items.length ? [['l-info', '> 8-K items: ' + itemNames(f.items).join('; ')]] : []).concat([['l-mut', '  section changes and scores appear once ORACLE deep-parses it']]);
      stages[4].lines = [['l-ok', '> \u2713 Indexed \u00b7 cites ' + f.accession]];
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
      '<div class="stats"><div class="stat"><b class="' + (f.real && !f.measured ? 'c-accent' : matClass(f.materiality)) + '">' + (f.real && !f.measured ? '\u2013' : Math.round(f.materiality * 100)) + '</b><span>Materiality</span></div>' +
      '<div class="stat"><b class="c-amber">' + diffs.length + '</b><span>Changes</span></div>' +
      (f.live ? '<div class="stat"><b class="c-accent">' + f.sections.length + '</b><span>Sections</span></div></div>'
        : f.real ? '<div class="stat"><b class="c-accent">' + (f.row && f.row.size ? fmtKB(f.row.size) : '\u2013') + '</b><span>Document</span></div></div>'
        : '<div class="stat"><b class="c-accent">' + secs + 's</b><span>Crawl time</span></div></div>') +
      '<dl class="prov"><dt>Source</dt><dd class="mono">' + esc(src) + '</dd><dt>SHA-256</dt><dd class="mono">' + (f.sha256 ? f.sha256.slice(0, 32) + '\u2026' : f.real ? 'computed when ORACLE downloads it' : sha(t + f.id).slice(0, 32) + '\u2026') + '</dd>' +
      '<dt>Period</dt><dd>' + esc(f.date) + '</dd><dt>Version</dt><dd>' + (f.live || f.real ? (f.is_amendment ? 'amendment' + (f.amends ? ' of ' + esc(f.amends) : '') : 'original') : 'v1 \u00b7 original preserved') + '</dd></dl></div>' +
      (f.real && !f.live
        ? '<p class="panel-foot"><span class="live-tag">SEC EDGAR</span> <a href="' + esc(f.sec_url) + '" target="_blank" rel="noopener">Open the document</a> \u00b7 <a href="' + esc(f.index_url) + '" target="_blank" rel="noopener">filing index</a> \u00b7 Listed live from SEC EDGAR. Not deep-parsed by ORACLE yet, so there are no section changes or scores for it.</p>'
        : f.live
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
    panelBody.innerHTML = '<div class="diff-head">' + (f.real && !f.live ? 'Filing details for <b>' + esc(f.id) + '</b>' : f.live && !f.compared_to ? 'No earlier ' + esc(f.form) + ' in the crawl window for <b>' + esc(f.id) + '</b>'
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
    if (f.real && !f.measured) {
      panelBody.innerHTML = '<div class="diff-head">Not scored yet</div><p class="panel-foot">Scores come from comparing a filing\u2019s text with the previous version. ' +
        (f.live ? 'There is no earlier ' + esc(f.form) + ' in the crawl window to compare with.' : 'This filing is listed live from SEC EDGAR but has not been deep-parsed by the ORACLE crawler yet.') +
        ' Deep-parsed today: 10-K, 10-Q, 8-K, DEF 14A and Form 4 for the 20 featured companies.</p>';
      return;
    }
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
    var cmd = q.match(/^(add|watch|track|open|show|remove|drop|close)\s+([a-z0-9.\-]{1,10})\b/);
    if (cmd) {
      var raw = cmd[2].toUpperCase();
      loadUniverse().then(function () {
        var t = ensureTicker(raw);
        if (!t) { aiMessage({ text: raw + ' is not an SEC-listed ticker I can find. Try the company name in the search box.' }); return; }
        if (/remove|drop|close/.test(cmd[1])) { removeStock(t); aiMessage({ text: 'Removed ' + t + ' from your watchlist.' }); return; }
        openTab(t);
        aiMessage({ text: 'Opened ' + t + ' (' + TICKER_DB[t].name + '). The crawler is reading its filing history from SEC EDGAR now; ask me anything about it here.' });
      });
      return;
    }
    if (/load demo|demo hive/.test(q)) { loadDemo(); aiMessage({ text: 'Loading a demo hive of five companies. Shared shareholders and deals will start linking the clusters as they appear.' }); return; }
    if (atts.length) { respondDoc(atts[0], msg); return; }
    var fm = findForm(msg);
    if (fm && mode === 'chat' && /what|explain|mean|is a|tell me|define|which|\?/.test(q)) { respondForm(fm); return; }
    if (!activeStock) {
      aiMessage({ text: 'Open a company first so I have filings to work with. Type "open NVDA", search any public company, or load the demo hive.', after: '<div class="actions"><button type="button" class="btn btn-ghost btn-sm" data-act="demo">Load demo hive</button><button type="button" class="btn btn-ghost btn-sm" data-act="add-NVDA">Add NVDA</button></div>' });
      return;
    }
    if (isReal(activeStock)) {
      if (mode === 'report') return respondRealReport(activeStock);
      return respondReal(q, activeStock);
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

  /* ---------- answers from real SEC data (any public company) ---------- */
  function rowCites(t, rows) {
    if (!rows.length) return '';
    return '<div class="cites" style="margin-top:8px">' + rows.slice(0, 4).map(function (r, i) {
      return '<button type="button" class="cite" data-cite-acc="' + esc(t) + '|' + esc(r.accession) + '">[' + (i + 1) + '] ' + esc(t + ' ' + rowLabel(r) + ' ' + fmtDate(r.date)) + '</button>';
    }).join('') + '</div>';
  }
  function within(t, test, days) { return SEC[t].filings.filter(function (r) { return test(r) && daysAgo(r.date) <= days; }); }
  function topCounts(rows, keyFn, n) {
    var c = {};
    rows.forEach(function (r) { (keyFn(r) || []).forEach(function (k) { c[k] = (c[k] || 0) + 1; }); });
    return Object.keys(c).sort(function (a, b) { return c[b] - c[a]; }).slice(0, n).map(function (k) { return [k, c[k]]; });
  }
  function respondReal(q, t) {
    var s = SEC[t], info = TICKER_DB[t], name = info.name;
    if (!s || s.status === 'loading') { aiMessage({ text: 'Still reading ' + t + '\u2019s filing history from SEC EDGAR. Ask again in a second.' }); return; }
    if (s.status !== 'ok') { aiMessage({ text: 'I could not reach SEC EDGAR for ' + t + ' (' + s.error + '). Check the connection and reopen the tab.' }); return; }
    var text, rows = [], openDiff = null, is = function (code) { return function (r) { return r.code === code; }; };
    var periodic = s.filings.filter(function (r) { return /^(10-K|10-Q|20-F|40-F)$/.test(r.code); });
    if (/insider|form 4|\b144\b|ownership|bought|sold|selling|buying/.test(q)) {
      var f4 = within(t, is('Form 4'), 90), f144 = within(t, is('Form 144'), 90), f4y = within(t, is('Form 4'), 365);
      text = name + ' has ' + f4.length + ' Form 4 insider transaction report' + (f4.length === 1 ? '' : 's') + ' in the last 90 days (' + f4y.length + ' in 12 months) and ' + f144.length + ' Form 144 proposed-sale notice' + (f144.length === 1 ? '' : 's') + '.' +
        (f4[0] ? ' The latest Form 4 was filed ' + fmtDate(f4[0].date) + '.' : '') + ' A Form 4 reports the trade itself (buy, sale, option exercise or grant) within two business days; open the citations to read the transaction tables on EDGAR.';
      rows = f4.slice(0, 3).concat(f144.slice(0, 1));
    } else if (/8-k|event|announce|news|current report/.test(q)) {
      var ek = within(t, is('8-K'), 365), it = topCounts(ek, function (r) { return r.items; }, 4);
      text = name + ' filed ' + ek.length + ' Form 8-K current report' + (ek.length === 1 ? '' : 's') + ' in the last 12 months.' +
        (it.length ? ' Most common items: ' + it.map(function (x) { return x[0] + ' ' + (ITEM_8K[x[0]] || '') + ' (' + x[1] + ')'; }).join(', ') + '.' : '') +
        (ek[0] ? ' Latest: ' + fmtDate(ek[0].date) + (ek[0].items.length ? ', items ' + itemNames(ek[0].items).join('; ') : '') + '.' : '');
      rows = ek.slice(0, 3);
    } else if (/risk|change|diff|prior|\bvs\b|new language|what changed|compare/.test(q)) {
      var lf = getFilings(t).filter(function (f) { return f.live && f.measured; })[0];
      if (lf) {
        var parts = lf.sections.filter(function (x) { return x.change; }).map(function (x) {
          return (LIVE_SECTION[x.key] || x.title) + ' +' + x.change.paragraphs_added + ' new, ' + x.change.paragraphs_modified + ' reworded, ' + x.change.paragraphs_removed + ' dropped';
        });
        var rf = lf.sections.filter(function (x) { return x.key === 'risk_factors' && x.change && x.change.added_samples.length; })[0];
        text = 'Comparing ' + t + '\u2019s ' + lf.id + ' with the prior ' + lf.form + ' (' + lf.compared_to + '), paragraph by paragraph: ' + parts.join('; ') + '.' +
          (rf ? ' First new risk-factor passage: \u201c' + rf.change.added_samples[0].slice(0, 220) + (rf.change.added_samples[0].length > 220 ? '\u2026' : '') + '\u201d' : '') + ' The Changes tab has every passage with before and after.';
        rows = [lf.row]; openDiff = lf;
      } else {
        var p = periodic[0];
        text = 'I have ' + name + '\u2019s full filing list live from SEC, but paragraph-level comparisons come from the ORACLE crawler, which has deep-parsed the 20 featured companies so far. ' +
          (p ? 'The latest periodic report is a ' + rowLabel(p) + ' filed ' + fmtDate(p.date) + (p.report ? ' for the period ending ' + p.report : '') + '. ' : '') +
          'For any company I can already answer about insider trades, 8-K events, offerings, amendments and filing history.';
        rows = periodic.slice(0, 2);
      }
    } else if (/10-k|annual|20-f/.test(q)) {
      var ak = s.filings.filter(function (r) { return /^(10-K|20-F|40-F)$/.test(r.code); });
      text = ak.length ? name + '\u2019s latest annual report is a ' + rowLabel(ak[0]) + ' filed ' + fmtDate(ak[0].date) + (ak[0].report ? ' for the fiscal year ending ' + ak[0].report : '') + '. ' + ak.length + ' annual reports are in the loaded history.' : 'No annual report (10-K, 20-F or 40-F) in the loaded history for ' + name + '.';
      rows = ak.slice(0, 2);
    } else if (/10-q|quarter/.test(q)) {
      var qk = s.filings.filter(is('10-Q'));
      text = qk.length ? 'Latest 10-Q: filed ' + fmtDate(qk[0].date) + (qk[0].report ? ' for the quarter ending ' + qk[0].report : '') + '. ' + within(t, is('10-Q'), 365).length + ' quarterly reports in the last 12 months.' : name + ' has no 10-Q in the loaded history (foreign filers report on 6-K instead).';
      rows = qk.slice(0, 3);
    } else if (/proxy|def 14a|compensation|\bvote|board|director|governance/.test(q)) {
      var px = s.filings.filter(function (r) { return /^(DEF 14A|DEFA14A|PRE 14A|DEFM14A|DEFC14A)$/.test(r.code); });
      var gov = within(t, function (r) { return r.code === '8-K' && r.items.some(function (i) { return /^5\.0[2378]$/.test(i); }); }, 365);
      text = (px[0] ? 'Latest proxy material: ' + rowLabel(px[0]) + ' filed ' + fmtDate(px[0].date) + '. ' : 'No proxy statement in the loaded history. ') +
        gov.length + ' 8-K' + (gov.length === 1 ? '' : 's') + ' in the last year covered governance items (officer or director changes, bylaws, shareholder votes).';
      rows = px.slice(0, 2).concat(gov.slice(0, 2));
    } else if (/offering|raise|capital|s-1|s-3|424|shelf|dilut|prospectus|debt|notes/.test(q)) {
      var off = within(t, function (r) { return r.cat === 'offerings' || r.cat === 'debt'; }, 365), fc = topCounts(off, function (r) { return [rowLabel(r)]; }, 4);
      text = off.length + ' capital-markets or debt filings in the last 12 months' + (fc.length ? ': ' + fc.map(function (x) { return x[0] + ' (' + x[1] + ')'; }).join(', ') : '') + '. Prospectus supplements (424B) and shelf registrations (S-3) usually mean securities were offered.';
      rows = off.slice(0, 3);
    } else if (/late|nt 10|amend|restat|non-reliance|auditor/.test(q)) {
      var am = within(t, function (r) { return r.amend; }, 730), nt = within(t, function (r) { return /^NT /.test(r.code); }, 730), rs = within(t, function (r) { return r.items.indexOf('4.02') >= 0 || r.items.indexOf('4.01') >= 0; }, 730);
      text = 'Over the last two years: ' + am.length + ' amended filings, ' + nt.length + ' late-filing notices (NT 10-K / NT 10-Q), and ' + rs.length + ' 8-K' + (rs.length === 1 ? '' : 's') + ' about auditor changes or non-reliance on past financials.' +
        (nt.length || rs.length ? ' Those are worth reading first.' : ' No red flags of that kind.');
      rows = rs.concat(nt).concat(am).slice(0, 4);
    } else if (/latest|recent|new|last/.test(q)) {
      rows = s.filings.slice(0, 5);
      text = 'Most recent ' + t + ' filings: ' + rows.map(function (r) { return rowLabel(r) + ' on ' + fmtDate(r.date) + (r.items.length ? ' (' + r.items.join(', ') + ')' : ''); }).join('; ') + '.';
    } else {
      var yr = within(t, function () { return true; }, 365), mix = topCounts(yr, function (r) { return [rowLabel(r)]; }, 5);
      text = name + (info.sector ? ' (' + info.sector + ')' : '') + ': ' + yr.length + ' SEC filings in the last 12 months' + (mix.length ? ', mostly ' + mix.map(function (x) { return x[0] + ' \u00d7' + x[1]; }).join(', ') : '') + '. ' +
        (periodic[0] ? 'Latest periodic report: ' + rowLabel(periodic[0]) + ' on ' + fmtDate(periodic[0].date) + '. ' : '') +
        (LIVE[t] ? 'ORACLE has deep-parsed its recent filings, so ask what changed in the risk factors or MD&A. ' : '') +
        'Try: insider activity, 8-K events, offerings, amendments, or the latest 10-K.';
      rows = periodic.slice(0, 1).concat(s.filings.slice(0, 2));
    }
    aiMessage({ kicker: t + ' \u00b7 live SEC data', text: text, after: rowCites(t, rows), done: function () {
      if (openDiff) { openPanel(openDiff, t); setTab('diff'); }
    } });
  }
  function respondRealReport(t) {
    var s = SEC[t], info = TICKER_DB[t], yr = within(t, function () { return true; }, 365);
    var periodic = s.filings.filter(function (r) { return /^(10-K|10-Q|20-F|40-F)$/.test(r.code); });
    var mix = topCounts(yr, function (r) { return [rowLabel(r)]; }, 8), ek = within(t, function (r) { return r.code === '8-K'; }, 365);
    var lf = getFilings(t).filter(function (f) { return f.live && f.measured; })[0], today = new Date().toISOString().slice(0, 10);
    var md = '# ' + t + ' filing brief\n\n' + info.name + ' | CIK ' + pad10(info.cik) + ' | ' + today + ' | source: SEC EDGAR (live) | not investment advice\n\n' +
      '## Activity, last 12 months\n\n' + yr.length + ' filings: ' + mix.map(function (x) { return x[0] + ' x' + x[1]; }).join(', ') + '\n\n' +
      '## Latest periodic report\n\n' + (periodic[0] ? rowLabel(periodic[0]) + ' filed ' + periodic[0].date + ' (' + periodic[0].url + ')' : 'none in loaded history') + '\n\n' +
      '## 8-K events\n\n' + (ek.length ? ek.slice(0, 8).map(function (r) { return '- ' + r.date + ': ' + itemNames(r.items).join('; ') + ' (' + r.url + ')'; }).join('\n') : 'none in the last 12 months') + '\n\n' +
      (lf ? '## What changed in ' + lf.id + ' (vs ' + lf.compared_to + ')\n\n' + lf.sections.filter(function (x) { return x.change; }).map(function (x) {
        return '- ' + (LIVE_SECTION[x.key] || x.title) + ': +' + x.change.paragraphs_added + ' new, ' + x.change.paragraphs_modified + ' reworded, ' + x.change.paragraphs_removed + ' dropped' + (x.change.added_samples[0] ? '\n  - new: "' + x.change.added_samples[0] + '"' : '');
      }).join('\n') + '\n\n' : '') +
      '## Sources\n\n' + s.filings.slice(0, 5).map(function (r, i) { return '[' + (i + 1) + '] ' + rowLabel(r) + ' ' + r.accession + ' ' + r.url; }).join('\n') + '\n';
    lastReport = { t: t, md: md };
    var html = '<div class="report"><h3>' + esc(t) + ' filing brief</h3><p class="mono" style="font-size:11.5px;color:#949db2">' + esc(info.name) + ' \u00b7 ' + today + ' \u00b7 live from SEC EDGAR</p>' +
      '<h4>Activity, last 12 months</h4><p>' + yr.length + ' filings: ' + esc(mix.map(function (x) { return x[0] + ' \u00d7' + x[1]; }).join(', ')) + '</p>' +
      '<h4>8-K events</h4><ul>' + (ek.slice(0, 4).map(function (r) { return '<li>' + esc(fmtDate(r.date) + ': ' + itemNames(r.items).join('; ')) + '</li>'; }).join('') || '<li>None in the last 12 months</li>') + '</ul>' +
      (lf ? '<h4>What changed in ' + esc(lf.id) + '</h4><ul>' + lf.sections.filter(function (x) { return x.change; }).map(function (x) { return '<li>' + esc((LIVE_SECTION[x.key] || x.title) + ': +' + x.change.paragraphs_added + ' new, ' + x.change.paragraphs_modified + ' reworded, ' + x.change.paragraphs_removed + ' dropped') + '</li>'; }).join('') + '</ul>' : '') +
      '<h4>Sources</h4>' + rowCites(t, s.filings.slice(0, 3)) +
      '<div class="actions"><button type="button" class="btn btn-ghost btn-sm" data-act="dl">Download .md</button><button type="button" class="btn btn-ghost btn-sm" data-act="copy">Copy</button></div></div>';
    aiMessage({ kicker: 'Report \u00b7 ' + t + ' \u00b7 live SEC data', html: html });
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
    if (R.md) return R.md;
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
    var ca = e.target.closest('[data-cite-acc]');
    if (ca) {
      var pa = ca.getAttribute('data-cite-acc').split('|'), fa = filingByAccession(pa[0], pa[1]);
      if (fa) { if (activeTab !== pa[0]) openTab(pa[0]); openPanel(fa, pa[0]); }
      return;
    }
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
  renderTabs();
  var fromUrl = (new URLSearchParams(location.search).get('t') || '').split(',').map(normTicker).filter(Boolean);
  var saved = store(WL_KEY), savedTabs = store(TABS_KEY) || {};
  renderSidebar();
  updateTopbar();
  setIdleStatus();
  updateGraph();
  loadUniverse().then(function () { buildShell(); if (!cam.userZoom) cam.tz = targetZoom(); kick(); });
  Promise.all([loadUniverse(), liveInit([])]).then(function () {
    var initial = (fromUrl.length ? fromUrl : (Array.isArray(saved) ? saved : [])).map(ensureTicker).filter(Boolean);
    initial.forEach(function (t) { addStock(t, { instant: true, noSelect: true }); });
    if (fromUrl.length === 1 && initial[0]) { openTab(initial[0]); return; }
    if (!fromUrl.length) {
      (savedTabs.open || []).forEach(function (t) { t = ensureTicker(t); if (t && pinned.indexOf(t) >= 0 && openTabs.indexOf(t) < 0) openTabs.push(t); });
      if (savedTabs.active && openTabs.indexOf(savedTabs.active) >= 0) { switchTab(savedTabs.active); return; }
    }
    switchTab('hive');
  });
})();
