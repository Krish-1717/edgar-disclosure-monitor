/*
 * filings.js - the complete filing catalog shared by the landing page and the app.
 * Categories, every form we cover, tier priorities, and the intelligence features.
 * Pure ASCII (see CLAUDE.md).
 */
(function () {
  'use strict';

  var CATEGORIES = {
    financial:   { label: 'Financial reporting', short: 'Financial', color: '#a8b4ff',
                   blurb: 'The core documents investors use to understand financial performance. The foundation of the analysis engine.' },
    governance:  { label: 'Governance & proxy', short: 'Governance', color: '#67e8f9',
                   blurb: 'How a company is governed and what shareholders are being asked to approve.' },
    insider:     { label: 'Insider & ownership', short: 'Insider', color: '#f5c97a',
                   blurb: 'Changes in insider ownership and significant shareholder positions.' },
    offerings:   { label: 'Capital markets & offerings', short: 'Offerings', color: '#b794ff',
                   blurb: 'Filed when companies raise capital, issue shares or restructure their securities.' },
    ma:          { label: 'M&A & corporate transactions', short: 'M&A', color: '#f9a8d4',
                   blurb: 'Critical for investment banking, M&A research and event-driven investing.' },
    debt:        { label: 'Debt, credit & financing', short: 'Debt', color: '#7dd3fc',
                   blurb: 'Financial obligations and capital structure: issuance, covenants, maturities.' },
    specialized: { label: 'Specialized regulatory', short: 'Specialized', color: '#c3cce6',
                   blurb: 'Disclosures for particular industries, structures or circumstances.' },
    other:       { label: 'Other investor documents', short: 'Other', color: '#86efac',
                   blurb: 'Not always standalone SEC filings: some are exhibits, others live on investor-relations sites.' }
  };
  var CAT_ORDER = ['financial', 'governance', 'insider', 'offerings', 'ma', 'debt', 'specialized', 'other'];

  var TIERS = {
    1: { label: 'Tier 1', name: 'Essential', note: 'Build first' },
    2: { label: 'Tier 2', name: 'Advanced intelligence', note: 'Build next' },
    3: { label: 'Tier 3', name: 'Specialized coverage', note: 'Expand later' }
  };

  // code, name, what it contains, categories (first = primary), tier (0 = standard coverage)
  var CATALOG = [
    ['10-K', 'Annual Report', 'Full-year financial statements, business overview, risks, management discussion and audited financials. Also debt schedules, maturities, covenants and liquidity.', ['financial', 'debt'], 1],
    ['10-Q', 'Quarterly Report', 'Quarterly financial statements, performance updates, risks and management discussion. Also interim debt and liquidity disclosures.', ['financial', 'debt'], 1],
    ['8-K', 'Current Report', 'Significant events: acquisitions, executive departures, bankruptcies, material agreements, new debt, credit agreements, defaults and deal closings.', ['financial', 'ma', 'debt'], 1],
    ['20-F', 'Foreign Annual Report', 'Annual reporting for foreign private issuers.', ['financial'], 3],
    ['6-K', 'Foreign Current Report', 'Material updates from foreign private issuers.', ['financial'], 3],
    ['11-K', 'Employee Benefit Plan Report', 'Annual financial information about certain employee benefit plans.', ['financial'], 3],

    ['DEF 14A', 'Definitive Proxy Statement', 'Executive compensation, board members, shareholder proposals and voting matters.', ['governance'], 1],
    ['PRE 14A', 'Preliminary Proxy', 'Preliminary version of the proxy statement.', ['governance'], 0],
    ['DEFA14A', 'Additional Proxy Materials', 'Supplemental shareholder communications.', ['governance'], 0],
    ['DEF 14C', 'Information Statement', 'Corporate actions communicated to shareholders without a traditional shareholder vote.', ['governance'], 0],
    ['DEFM14A', 'Merger Proxy', 'Merger terms, financial analysis, fairness opinions, recommendations and shareholder voting information.', ['governance', 'ma'], 2],
    ['DEFC14A', 'Contested Proxy', 'Proxy materials associated with a contested solicitation.', ['governance'], 0],

    ['Form 3', 'Initial Insider Ownership', 'Initial holdings when someone becomes a reporting insider.', ['insider'], 2],
    ['Form 4', 'Insider Transaction Report', 'Purchases, sales and other changes in insider ownership.', ['insider'], 1],
    ['Form 5', 'Annual Insider Report', 'Certain transactions not previously reported.', ['insider'], 2],
    ['Form 144', 'Notice of Proposed Sale', 'Proposed sales of restricted or control securities.', ['insider'], 3],
    ['SC 13D', 'Active Ownership Disclosure', 'Large shareholder ownership and potentially activist intentions.', ['insider'], 2],
    ['SC 13G', 'Passive Ownership Disclosure', 'Significant ownership by qualifying passive investors.', ['insider'], 2],
    ['13F-HR', 'Institutional Holdings', 'Quarterly holdings disclosures from qualifying institutional investment managers.', ['insider'], 2],

    ['S-1', 'Registration Statement', 'IPOs and certain new securities offerings.', ['offerings'], 1],
    ['S-3', 'Shelf Registration', 'Registration for eligible future equity or debt offerings.', ['offerings', 'debt'], 2],
    ['S-4', 'Business Combination Registration', 'Securities issued in mergers and acquisitions.', ['offerings', 'ma'], 1],
    ['S-8', 'Employee Stock Plan Registration', 'Shares registered for employee compensation plans.', ['offerings'], 0],
    ['424B3', 'Prospectus', 'Final or updated offering information.', ['offerings'], 2],
    ['424B5', 'Prospectus Supplement', 'Additional details about a securities offering.', ['offerings'], 2],
    ['F-1', 'Foreign IPO Registration', 'Registration for foreign private issuers.', ['offerings'], 0],
    ['F-3', 'Foreign Shelf Registration', 'Securities offerings by eligible foreign issuers.', ['offerings'], 0],

    ['SC TO-T', 'Third-Party Tender Offer', 'An outside party\'s offer to purchase a company\'s shares.', ['ma'], 2],
    ['SC TO-I', 'Issuer Tender Offer', 'A company\'s offer to repurchase its own securities.', ['ma'], 0],
    ['SC 14D9', 'Tender Offer Recommendation', 'Target company\'s position and recommendation regarding a tender offer.', ['ma'], 0],
    ['425', 'Business Combination Communications', 'Communications relating to a business combination involving securities.', ['ma'], 0],
    ['PREM14A', 'Preliminary Merger Proxy', 'Preliminary merger-related shareholder materials.', ['ma'], 0],

    ['424B2', 'Prospectus (debt)', 'Certain debt and securities offering information.', ['debt'], 2],
    ['FWP', 'Free Writing Prospectus', 'Additional offering communications.', ['debt'], 0],

    ['SD', 'Specialized Disclosure Report', 'Certain resource extraction and other specialized disclosures.', ['specialized'], 3],
    ['13F-NT', 'Institutional Holdings Notice', 'Notice relating to institutional holdings reporting.', ['specialized'], 3],
    ['10-D', 'Asset-Backed Distribution Report', 'Periodic information about asset-backed securities.', ['specialized'], 3],
    ['ABS-EE', 'Asset-Backed Securities Exhibit', 'Asset-level information supporting certain ABS disclosures.', ['specialized'], 3],
    ['NT 10-K', 'Late Annual Filing Notice', 'Notice that a company cannot file its 10-K on time.', ['specialized'], 3],
    ['NT 10-Q', 'Late Quarterly Filing Notice', 'Notice that a company cannot file its 10-Q on time.', ['specialized'], 3],
    ['15-12B', 'Registration Termination (exchange)', 'Notice concerning termination of exchange-listed registration.', ['specialized'], 3],
    ['15-12G', 'Registration Termination', 'Notice concerning termination of registration or reporting obligations.', ['specialized'], 3],

    ['ARS', 'Annual Report to Shareholders', 'Management\'s annual communication to investors.', ['other'], 0],
    ['EX-99 Earnings', 'Earnings Press Release', 'Quarterly or annual earnings announcements.', ['other'], 0],
    ['Earnings Deck', 'Earnings Presentation', 'Management\'s financial performance presentation.', ['other'], 0],
    ['Transcript', 'Earnings Call Transcript', 'Management commentary and analyst questions.', ['other'], 0],
    ['Investor Deck', 'Investor Presentation', 'Company strategy, forecasts and business outlook.', ['other'], 0],
    ['Letter', 'Shareholder Letter', 'Management\'s views on performance and future direction.', ['other'], 0],
    ['EX-4 Debt', 'Debt Agreement', 'Loan terms, restrictions, covenants and repayment obligations.', ['other', 'debt'], 0],
    ['Rating', 'Credit Rating Report', 'Creditworthiness assessments from rating agencies.', ['other', 'debt'], 0],
    ['EX-10', 'Material Contract', 'Commercial agreements, acquisitions, partnerships and financing arrangements.', ['other'], 0]
  ].map(function (r) { return { code: r[0], name: r[1], desc: r[2], cats: r[3], cat: r[3][0], tier: r[4] }; });

  var BY_CODE = {};
  CATALOG.forEach(function (f) { BY_CODE[f.code] = f; });

  var FEATURES = [
    { name: 'Filing Intelligence', text: 'Reads and summarizes every SEC filing.' },
    { name: 'Change Detection', text: 'Identifies exactly what changed between two filings.' },
    { name: 'Risk Detection', text: 'Finds new risks, deteriorating conditions and concerning language.' },
    { name: 'Financial Intelligence', text: 'Extracts metrics, debt, revenue, margins and guidance.' },
    { name: 'Event Intelligence', text: 'Detects acquisitions, executive changes, insider trades and material announcements.' }
  ];

  var AGENTS = [
    { name: 'Financial', text: 'Revenue, margins, cash flow, debt, liquidity and profitability.' },
    { name: 'Risk', text: 'Emerging financial, operational, legal and regulatory risks.' },
    { name: 'Historical diff', text: 'Newly introduced, removed, modified and contradictory disclosures.' },
    { name: 'Forensic', text: 'Unusual movements, accounting changes and warning signs.' },
    { name: 'Corporate intel', text: 'Connects executives, shareholders, subsidiaries, deals and competitors.' },
    { name: 'External research', text: 'Cross-references disclosures with authoritative outside sources.' }
  ];

  window.EDM_FILINGS = {
    CATEGORIES: CATEGORIES, CAT_ORDER: CAT_ORDER, TIERS: TIERS,
    CATALOG: CATALOG, BY_CODE: BY_CODE, FEATURES: FEATURES, AGENTS: AGENTS,
    tierOf: function (code) { var f = BY_CODE[code]; return f ? f.tier : 0; }
  };
})();
