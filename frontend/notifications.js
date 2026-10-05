/**
 * notifications.js — Notification UI enhancement for EDGAR Disclosure Monitor
 *
 * Standalone script that augments the existing SPA with:
 *  1. Notification bell in the nav bar (top right)
 *  2. Dropdown panel with last 5 notifications
 *  3. "Set Alert" button on alert cards
 *  4. "Alerts Setup" preferences tab (6th nav tab)
 *  5. Toast notification system
 *
 * Self-contained — inject after index.html loads:
 *   <script src="notifications.js"></script>
 */

(function () {
  'use strict';

  // -------------------------------------------------------------------------
  // Mock notification data (mirrors ALERTS structure from index.html)
  // -------------------------------------------------------------------------
  const NOTIFICATION_DATA = [
    {
      id: 'n1',
      ticker: 'NVDA',
      title: 'NVDA files 10-K — Attention Gap 85.2',
      body: 'AI chip export restriction risks disclosed in annual filing, absent from 94% of analyst reports. REGULATORY signal dominant.',
      severity: 'CRITICAL',
      source: 'COMBINED',
      attention_gap: 85.2,
      materiality_score: 0.87,
      news_quality_score: 0.71,
      sentiment: 'BEARISH',
      top_bucket: 'REGULATORY',
      ts: new Date(Date.now() - 1000 * 60 * 12).toISOString(),
      read: false,
      url: 'https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=NVDA&type=10-K',
    },
    {
      id: 'n2',
      ticker: 'JPM',
      title: 'JPM 10-K — Basel III risk factors under-covered',
      body: 'New capital buffer requirements discussed in detail. Analyst consensus materially silent on regulatory headwinds.',
      severity: 'HIGH',
      source: 'SEC_FILING',
      attention_gap: 62.1,
      materiality_score: 0.65,
      news_quality_score: 0.68,
      sentiment: 'BEARISH',
      top_bucket: 'REGULATORY',
      ts: new Date(Date.now() - 1000 * 60 * 45).toISOString(),
      read: false,
      url: 'https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=JPM&type=10-K',
    },
    {
      id: 'n3',
      ticker: 'MSFT',
      title: 'MSFT — REGULATORY news signal (quality 0.70)',
      body: '4 REGULATORY headlines in last 6 hours. FTC antitrust scrutiny of Azure AI pricing under SEC watch.',
      severity: 'HIGH',
      source: 'NEWS',
      attention_gap: 61.5,
      materiality_score: 0.0,
      news_quality_score: 0.70,
      sentiment: 'BEARISH',
      top_bucket: 'REGULATORY',
      ts: new Date(Date.now() - 1000 * 60 * 90).toISOString(),
      read: true,
      url: 'https://news.google.com/search?q=MSFT+FTC',
    },
    {
      id: 'n4',
      ticker: 'AAPL',
      title: 'AAPL 10-Q filed — Attention Gap 41.3',
      body: 'Services revenue growth slowing noted in MD&A. Minimal divergence from analyst consensus but above medium threshold.',
      severity: 'MEDIUM',
      source: 'SEC_FILING',
      attention_gap: 41.3,
      materiality_score: 0.42,
      news_quality_score: 0.52,
      sentiment: 'NEUTRAL',
      top_bucket: 'EARNINGS',
      ts: new Date(Date.now() - 1000 * 60 * 180).toISOString(),
      read: true,
      url: 'https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=AAPL&type=10-Q',
    },
    {
      id: 'n5',
      ticker: 'META',
      title: 'META — LEADERSHIP change detected in news',
      body: 'Board restructuring reported across 3 sources. LEADERSHIP bucket signal quality 0.67.',
      severity: 'MEDIUM',
      source: 'NEWS',
      attention_gap: 43.0,
      materiality_score: 0.0,
      news_quality_score: 0.67,
      sentiment: 'BEARISH',
      top_bucket: 'LEADERSHIP',
      ts: new Date(Date.now() - 1000 * 60 * 240).toISOString(),
      read: true,
      url: 'https://news.google.com/search?q=META+board+leadership',
    },
  ];

  // -------------------------------------------------------------------------
  // Severity colours (matching backend / email template)
  // -------------------------------------------------------------------------
  const SEVERITY_COLOR = {
    CRITICAL: '#dc2626',
    HIGH:     '#d97706',
    MEDIUM:   '#2563eb',
    LOW:      '#16a34a',
  };

  // -------------------------------------------------------------------------
  // Inject CSS
  // -------------------------------------------------------------------------
  function injectStyles() {
    const style = document.createElement('style');
    style.textContent = `
      /* Notification bell */
      #notif-bell-btn {
        position: relative;
        background: none;
        border: 1px solid #1e3a5f;
        border-radius: 6px;
        color: #94a3b8;
        cursor: pointer;
        padding: 6px 10px;
        font-size: 18px;
        transition: border-color .2s, color .2s;
        display: flex;
        align-items: center;
        gap: 6px;
      }
      #notif-bell-btn:hover { border-color: #00d4ff; color: #00d4ff; }
      #notif-badge {
        background: #dc2626;
        color: #fff;
        border-radius: 50%;
        font-size: 10px;
        font-weight: 700;
        min-width: 16px;
        height: 16px;
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 0 3px;
      }
      #notif-badge.hidden { display: none; }

      /* Dropdown */
      #notif-dropdown {
        position: absolute;
        top: calc(100% + 8px);
        right: 0;
        width: 380px;
        background: #0d1526;
        border: 1px solid #1e3a5f;
        border-radius: 10px;
        box-shadow: 0 20px 60px rgba(0,0,0,.6);
        z-index: 9999;
        overflow: hidden;
        display: none;
      }
      #notif-dropdown.open { display: block; }
      .notif-dd-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 12px 16px;
        border-bottom: 1px solid #1e3a5f;
        color: #e2e8f0;
        font-size: 13px;
        font-weight: 600;
      }
      .notif-dd-header a {
        color: #00d4ff;
        font-size: 11px;
        cursor: pointer;
        text-decoration: none;
      }
      .notif-item {
        padding: 12px 16px;
        border-bottom: 1px solid #0f1f3a;
        cursor: pointer;
        transition: background .15s;
        display: flex;
        gap: 10px;
        align-items: flex-start;
      }
      .notif-item:hover { background: #0f1f3a; }
      .notif-item.unread { background: #0a1624; }
      .notif-dot {
        width: 7px; height: 7px;
        border-radius: 50%;
        margin-top: 5px;
        flex-shrink: 0;
      }
      .notif-item-body { flex: 1; min-width: 0; }
      .notif-item-title {
        font-size: 12px;
        font-weight: 600;
        color: #e2e8f0;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        margin-bottom: 3px;
      }
      .notif-item-sub {
        font-size: 11px;
        color: #64748b;
        display: flex;
        gap: 8px;
        flex-wrap: wrap;
      }
      .notif-sev-badge {
        font-size: 10px;
        font-weight: 700;
        border-radius: 3px;
        padding: 1px 5px;
        color: #fff;
      }
      .notif-dd-footer {
        padding: 10px 16px;
        text-align: center;
        font-size: 11px;
        color: #475569;
        border-top: 1px solid #1e3a5f;
      }

      /* Set Alert button */
      .set-alert-btn {
        background: none;
        border: 1px solid #1e3a5f;
        border-radius: 5px;
        color: #64748b;
        font-size: 11px;
        padding: 4px 10px;
        cursor: pointer;
        transition: border-color .2s, color .2s;
        margin-top: 6px;
      }
      .set-alert-btn:hover { border-color: #00d4ff; color: #00d4ff; }

      /* Alert modal */
      #alert-modal-overlay {
        position: fixed; inset: 0;
        background: rgba(0,0,0,.65);
        z-index: 10000;
        display: flex;
        align-items: center;
        justify-content: center;
        display: none;
      }
      #alert-modal-overlay.open { display: flex; }
      #alert-modal {
        background: #0d1526;
        border: 1px solid #1e3a5f;
        border-radius: 10px;
        padding: 24px;
        width: 360px;
        max-width: 92vw;
      }
      #alert-modal h3 { margin: 0 0 12px; color: #e2e8f0; font-size: 15px; }
      #alert-modal p  { color: #94a3b8; font-size: 13px; margin: 0 0 14px; }
      #alert-modal input {
        width: 100%; box-sizing: border-box;
        background: #0a0f1a;
        border: 1px solid #1e3a5f;
        border-radius: 6px;
        color: #e2e8f0;
        font-size: 13px;
        padding: 8px 12px;
        margin-bottom: 14px;
      }
      .modal-actions { display: flex; gap: 10px; justify-content: flex-end; }
      .modal-btn {
        border-radius: 6px;
        font-size: 13px;
        font-weight: 600;
        padding: 8px 18px;
        cursor: pointer;
        border: none;
      }
      .modal-btn-primary { background: #1e40af; color: #fff; }
      .modal-btn-secondary { background: #1e3a5f; color: #94a3b8; }

      /* Alerts Setup tab content */
      #tab-alerts-setup {
        display: none;
        padding: 24px;
        color: #e2e8f0;
      }
      #tab-alerts-setup h2 {
        color: #00d4ff;
        font-size: 18px;
        margin: 0 0 6px;
      }
      #tab-alerts-setup p { color: #94a3b8; font-size: 13px; margin: 0 0 20px; }
      .setup-section { margin-bottom: 24px; }
      .setup-section label {
        display: block;
        color: #94a3b8;
        font-size: 12px;
        text-transform: uppercase;
        letter-spacing: .05em;
        margin-bottom: 8px;
      }
      .setup-input {
        background: #0a0f1a;
        border: 1px solid #1e3a5f;
        border-radius: 6px;
        color: #e2e8f0;
        font-size: 13px;
        padding: 8px 12px;
        width: 100%;
        max-width: 360px;
        box-sizing: border-box;
      }
      .threshold-options { display: flex; gap: 10px; flex-wrap: wrap; margin-top: 4px; }
      .threshold-opt {
        background: #0a1624;
        border: 1px solid #1e3a5f;
        border-radius: 6px;
        color: #94a3b8;
        font-size: 12px;
        font-weight: 600;
        padding: 6px 14px;
        cursor: pointer;
        transition: all .2s;
      }
      .threshold-opt.active {
        color: #fff;
        border-color: #00d4ff;
        background: #0d2040;
      }
      .test-btn {
        background: #1e3a5f;
        border: 1px solid #2563eb;
        border-radius: 6px;
        color: #93c5fd;
        font-size: 13px;
        font-weight: 600;
        padding: 10px 20px;
        cursor: pointer;
        transition: background .2s;
      }
      .test-btn:hover { background: #1e40af; }

      /* Toast */
      #toast-container {
        position: fixed;
        bottom: 24px;
        right: 24px;
        z-index: 20000;
        display: flex;
        flex-direction: column;
        gap: 10px;
        pointer-events: none;
      }
      .toast {
        background: #0d1526;
        border: 1px solid #1e3a5f;
        border-left: 4px solid #2563eb;
        border-radius: 8px;
        padding: 12px 16px;
        color: #e2e8f0;
        font-size: 13px;
        max-width: 320px;
        box-shadow: 0 8px 24px rgba(0,0,0,.5);
        animation: slideInRight .3s ease;
        pointer-events: auto;
      }
      .toast.critical { border-left-color: #dc2626; }
      .toast.high     { border-left-color: #d97706; }
      @keyframes slideInRight {
        from { transform: translateX(120%); opacity: 0; }
        to   { transform: translateX(0);    opacity: 1; }
      }
      @keyframes fadeOut {
        from { opacity: 1; }
        to   { opacity: 0; transform: translateY(10px); }
      }
    `;
    document.head.appendChild(style);
  }

  // -------------------------------------------------------------------------
  // Toast system
  // -------------------------------------------------------------------------
  let toastContainer;
  function initToasts() {
    toastContainer = document.createElement('div');
    toastContainer.id = 'toast-container';
    document.body.appendChild(toastContainer);
  }

  function showToast(message, severity = 'MEDIUM', duration = 4000) {
    const el = document.createElement('div');
    el.className = `toast ${(severity || '').toLowerCase()}`;
    el.textContent = message;
    toastContainer.appendChild(el);
    setTimeout(() => {
      el.style.animation = 'fadeOut .4s ease forwards';
      setTimeout(() => el.remove(), 400);
    }, duration);
  }

  // -------------------------------------------------------------------------
  // Notification bell
  // -------------------------------------------------------------------------
  let notifOpen = false;
  let notifications = NOTIFICATION_DATA.slice();

  function unreadCount() {
    return notifications.filter(n => !n.read).length;
  }

  function renderDropdown(dropdown) {
    const items = notifications.slice(0, 5);
    const unread = unreadCount();
    dropdown.innerHTML = `
      <div class="notif-dd-header">
        <span>Notifications ${unread > 0 ? `<span style="color:#dc2626">(${unread} new)</span>` : ''}</span>
        <a id="mark-all-read">Mark all read</a>
      </div>
      ${items.map(n => `
        <div class="notif-item ${n.read ? '' : 'unread'}" data-id="${n.id}">
          <div class="notif-dot" style="background:${SEVERITY_COLOR[n.severity] || '#64748b'}"></div>
          <div class="notif-item-body">
            <div class="notif-item-title">${n.title}</div>
            <div class="notif-item-sub">
              <span class="notif-sev-badge" style="background:${SEVERITY_COLOR[n.severity]}">${n.severity}</span>
              <span>${n.source}</span>
              <span>Gap ${(n.attention_gap || 0).toFixed(1)}</span>
              <span>${timeAgo(n.ts)}</span>
            </div>
          </div>
        </div>
      `).join('')}
      <div class="notif-dd-footer">
        ${notifications.length} total notifications — set up alerts below
      </div>
    `;
    dropdown.querySelector('#mark-all-read').addEventListener('click', (e) => {
      e.stopPropagation();
      notifications.forEach(n => n.read = true);
      refreshBadge();
      renderDropdown(dropdown);
    });
    dropdown.querySelectorAll('.notif-item').forEach(el => {
      el.addEventListener('click', () => {
        const id = el.dataset.id;
        const n = notifications.find(x => x.id === id);
        if (n) {
          n.read = true;
          refreshBadge();
          renderDropdown(dropdown);
          if (n.url) window.open(n.url, '_blank');
        }
      });
    });
  }

  function refreshBadge() {
    const badge = document.getElementById('notif-badge');
    if (!badge) return;
    const count = unreadCount();
    badge.textContent = count;
    badge.classList.toggle('hidden', count === 0);
  }

  function timeAgo(isoStr) {
    const diff = Date.now() - new Date(isoStr).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return 'just now';
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h ago`;
    return `${Math.floor(hrs / 24)}d ago`;
  }

  function injectBell(navEl) {
    const wrapper = document.createElement('div');
    wrapper.style.cssText = 'position:relative;display:inline-flex;align-items:center';

    const btn = document.createElement('button');
    btn.id = 'notif-bell-btn';
    btn.setAttribute('aria-label', 'Notifications');
    btn.innerHTML = `🔔 <span id="notif-badge" class="${unreadCount() === 0 ? 'hidden' : ''}">${unreadCount()}</span>`;

    const dropdown = document.createElement('div');
    dropdown.id = 'notif-dropdown';
    renderDropdown(dropdown);

    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      notifOpen = !notifOpen;
      dropdown.classList.toggle('open', notifOpen);
      if (notifOpen) renderDropdown(dropdown);
    });
    document.addEventListener('click', () => {
      notifOpen = false;
      dropdown.classList.remove('open');
    });
    dropdown.addEventListener('click', e => e.stopPropagation());

    wrapper.appendChild(btn);
    wrapper.appendChild(dropdown);

    // Insert before the last nav child (usually the access-code input area)
    const lastChild = navEl.lastElementChild;
    navEl.insertBefore(wrapper, lastChild);
  }

  // -------------------------------------------------------------------------
  // "Set Alert" buttons on alert cards
  // -------------------------------------------------------------------------
  let alertModalTarget = '';

  function openAlertModal(ticker) {
    alertModalTarget = ticker;
    const modal = document.getElementById('alert-modal-overlay');
    const title = document.getElementById('alert-modal-ticker');
    if (title) title.textContent = ticker;
    if (modal) modal.classList.add('open');
  }

  function injectAlertModal() {
    const overlay = document.createElement('div');
    overlay.id = 'alert-modal-overlay';
    overlay.innerHTML = `
      <div id="alert-modal">
        <h3>Set Alert for <span id="alert-modal-ticker"></span></h3>
        <p>Notify me when this ticker files a new 10-K or 10-Q with a significant attention gap.</p>
        <input id="alert-email-input" type="email" placeholder="your@email.com" />
        <div class="modal-actions">
          <button class="modal-btn modal-btn-secondary" id="modal-cancel">Cancel</button>
          <button class="modal-btn modal-btn-primary" id="modal-save">Save Alert</button>
        </div>
      </div>
    `;
    document.body.appendChild(overlay);

    document.getElementById('modal-cancel').addEventListener('click', () => {
      overlay.classList.remove('open');
    });
    overlay.addEventListener('click', (e) => {
      if (e.target === overlay) overlay.classList.remove('open');
    });
    document.getElementById('modal-save').addEventListener('click', () => {
      const email = document.getElementById('alert-email-input').value.trim();
      const existing = JSON.parse(localStorage.getItem('edgar_alerts') || '[]');
      const already = existing.find(a => a.ticker === alertModalTarget);
      if (!already) {
        existing.push({ ticker: alertModalTarget, email, created: new Date().toISOString() });
      } else {
        already.email = email;
      }
      localStorage.setItem('edgar_alerts', JSON.stringify(existing));
      overlay.classList.remove('open');
      showToast(`Alert set for ${alertModalTarget}! We'll notify ${email || 'you'} on new filings.`, 'MEDIUM');
    });
  }

  function addAlertButtonsToCards() {
    // Alert cards in the Alerts feed section typically have data-ticker or contain ticker text
    // We use a mutation observer to catch dynamically rendered cards
    const observer = new MutationObserver(() => {
      document.querySelectorAll('[data-ticker]:not([data-alert-btn])').forEach(card => {
        const ticker = card.dataset.ticker;
        if (!ticker) return;
        card.dataset.alertBtn = '1';
        const btn = document.createElement('button');
        btn.className = 'set-alert-btn';
        btn.textContent = '🔔 Set Alert';
        btn.addEventListener('click', (e) => {
          e.stopPropagation();
          openAlertModal(ticker);
        });
        card.appendChild(btn);
      });
    });
    observer.observe(document.body, { childList: true, subtree: true });
  }

  // -------------------------------------------------------------------------
  // Alerts Setup tab (6th nav tab)
  // -------------------------------------------------------------------------
  let currentThreshold = 'HIGH';

  function injectAlertsSetupTab() {
    // Add the tab content panel
    const tabContent = document.createElement('div');
    tabContent.id = 'tab-alerts-setup';
    tabContent.innerHTML = `
      <h2>🔔 Alerts Setup</h2>
      <p>Configure when and how you receive notifications about SEC filings and news signals.</p>

      <div class="setup-section">
        <label>Email Address</label>
        <input id="setup-email" class="setup-input" type="email" placeholder="your@email.com" />
      </div>

      <div class="setup-section">
        <label>Notification Threshold</label>
        <p style="font-size:12px;color:#64748b;margin:0 0 8px">
          Higher thresholds mean fewer, more important alerts only.
        </p>
        <div class="threshold-options">
          <div class="threshold-opt ${currentThreshold === 'CRITICAL' ? 'active' : ''}" data-t="CRITICAL">CRITICAL only (gap ≥ 80)</div>
          <div class="threshold-opt ${currentThreshold === 'HIGH' ? 'active' : ''}"     data-t="HIGH">HIGH+ (gap ≥ 60)</div>
          <div class="threshold-opt ${currentThreshold === 'MEDIUM' ? 'active' : ''}"   data-t="MEDIUM">MEDIUM+ (gap ≥ 40)</div>
          <div class="threshold-opt ${currentThreshold === 'ALL' ? 'active' : ''}"      data-t="ALL">ALL (gap ≥ 20)</div>
        </div>
      </div>

      <div class="setup-section">
        <label>Enrolled Tickers</label>
        <p style="font-size:12px;color:#64748b;margin:0 0 8px">
          Tickers from your watchlist are auto-enrolled. Add more below.
        </p>
        <div id="enrolled-tickers" style="display:flex;flex-wrap:wrap;gap:8px;margin-bottom:10px"></div>
        <input id="add-ticker-input" class="setup-input" style="max-width:200px"
               placeholder="Add ticker (e.g. TSLA)" />
      </div>

      <div class="setup-section">
        <label>Test Notification</label>
        <p style="font-size:12px;color:#64748b;margin:0 0 8px">
          Sends a sample CRITICAL alert to verify your setup.
        </p>
        <button class="test-btn" id="test-notif-btn">Send Test Notification</button>
      </div>

      <div class="setup-section">
        <label>Recent Notifications</label>
        <div id="setup-notif-list" style="display:flex;flex-direction:column;gap:8px;max-width:600px"></div>
      </div>
    `;
    document.body.appendChild(tabContent);

    // Threshold selection
    tabContent.querySelectorAll('.threshold-opt').forEach(el => {
      el.addEventListener('click', () => {
        tabContent.querySelectorAll('.threshold-opt').forEach(o => o.classList.remove('active'));
        el.classList.add('active');
        currentThreshold = el.dataset.t;
        const prefs = JSON.parse(localStorage.getItem('edgar_notif_prefs') || '{}');
        prefs.threshold = currentThreshold;
        localStorage.setItem('edgar_notif_prefs', JSON.stringify(prefs));
        showToast(`Threshold set to ${currentThreshold}+`, 'LOW');
      });
    });

    // Email save on blur
    const emailInput = document.getElementById('setup-email');
    const savedPrefs = JSON.parse(localStorage.getItem('edgar_notif_prefs') || '{}');
    if (savedPrefs.email) emailInput.value = savedPrefs.email;
    emailInput.addEventListener('blur', () => {
      const prefs = JSON.parse(localStorage.getItem('edgar_notif_prefs') || '{}');
      prefs.email = emailInput.value;
      localStorage.setItem('edgar_notif_prefs', JSON.stringify(prefs));
    });

    // Test button
    document.getElementById('test-notif-btn').addEventListener('click', () => {
      const testNotif = {
        id: 'test-' + Date.now(),
        ticker: 'TEST',
        title: 'Test Notification — EDGAR Monitor Active',
        body: 'Your notification system is working. This is a simulated CRITICAL alert.',
        severity: 'CRITICAL',
        source: 'COMBINED',
        attention_gap: 95.0,
        materiality_score: 0.95,
        news_quality_score: 0.80,
        sentiment: 'BEARISH',
        top_bucket: 'REGULATORY',
        ts: new Date().toISOString(),
        read: false,
        url: '#',
      };
      notifications.unshift(testNotif);
      refreshBadge();
      showToast('🔔 TEST: EDGAR Monitor notification system is active!', 'CRITICAL', 5000);
    });

    // Enrolled tickers from localStorage
    function renderEnrolled() {
      const alerts = JSON.parse(localStorage.getItem('edgar_alerts') || '[]');
      const container = document.getElementById('enrolled-tickers');
      if (!container) return;
      container.innerHTML = alerts.map(a => `
        <span style="background:#0a1624;border:1px solid #1e3a5f;border-radius:5px;
                     padding:4px 10px;font-size:12px;color:#00d4ff;display:inline-flex;
                     align-items:center;gap:6px">
          ${a.ticker}
          <span data-remove="${a.ticker}" style="cursor:pointer;color:#64748b">✕</span>
        </span>
      `).join('');
      container.querySelectorAll('[data-remove]').forEach(el => {
        el.addEventListener('click', () => {
          const t = el.dataset.remove;
          const updated = JSON.parse(localStorage.getItem('edgar_alerts') || '[]')
            .filter(a => a.ticker !== t);
          localStorage.setItem('edgar_alerts', JSON.stringify(updated));
          renderEnrolled();
        });
      });
    }
    renderEnrolled();

    document.getElementById('add-ticker-input').addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        const val = e.target.value.trim().toUpperCase();
        if (!val) return;
        const alerts = JSON.parse(localStorage.getItem('edgar_alerts') || '[]');
        if (!alerts.find(a => a.ticker === val)) {
          alerts.push({ ticker: val, email: '', created: new Date().toISOString() });
          localStorage.setItem('edgar_alerts', JSON.stringify(alerts));
        }
        e.target.value = '';
        renderEnrolled();
        showToast(`${val} added to alert watchlist`, 'LOW');
      }
    });

    // Recent notifications list
    function renderSetupNotifList() {
      const el = document.getElementById('setup-notif-list');
      if (!el) return;
      el.innerHTML = notifications.slice(0, 10).map(n => `
        <div style="background:#0a1624;border:1px solid #1e3a5f;border-radius:6px;padding:10px 14px">
          <div style="display:flex;gap:8px;align-items:center;margin-bottom:4px">
            <span style="font-size:11px;font-weight:700;color:${SEVERITY_COLOR[n.severity]}">${n.severity}</span>
            <span style="font-size:12px;color:#e2e8f0;font-weight:600">${n.ticker}</span>
            <span style="font-size:11px;color:#64748b;margin-left:auto">${timeAgo(n.ts)}</span>
          </div>
          <div style="font-size:12px;color:#94a3b8">${n.title}</div>
        </div>
      `).join('');
    }
    renderSetupNotifList();

    return tabContent;
  }

  function addAlertsNavTab(tabContent) {
    // Try to find the nav tabs container
    const navTabContainers = document.querySelectorAll('nav, [role="tablist"], .nav-tabs, .tabs');
    let tabsBar = navTabContainers[0];

    if (!tabsBar) {
      // Fallback: look for elements that have multiple sibling tab-like elements
      const candidates = document.querySelectorAll('a, button');
      for (const el of candidates) {
        if (el.textContent.trim().match(/^(Overview|Alerts|Filings|Analysis|Sectors)/i)) {
          tabsBar = el.parentElement;
          break;
        }
      }
    }

    if (tabsBar) {
      const tab = document.createElement('a');
      tab.textContent = '🔔 Alerts Setup';
      tab.style.cssText = 'cursor:pointer;color:#94a3b8;font-size:13px;font-weight:500;padding:8px 14px;';
      tab.addEventListener('click', (e) => {
        e.preventDefault();
        // Hide all tab content panels
        document.querySelectorAll('[id^="tab-"]').forEach(p => p.style.display = 'none');
        tabContent.style.display = 'block';
        // Update active state
        tabsBar.querySelectorAll('a, button').forEach(t => t.style.color = '#94a3b8');
        tab.style.color = '#00d4ff';
      });
      tabsBar.appendChild(tab);
    }
  }

  // -------------------------------------------------------------------------
  // Bootstrap — wait for DOM / nav to be ready
  // -------------------------------------------------------------------------
  function bootstrap() {
    injectStyles();
    initToasts();
    injectAlertModal();
    addAlertButtonsToCards();
    const tabContent = injectAlertsSetupTab();

    // Use MutationObserver to detect when nav is rendered
    const navObserver = new MutationObserver(() => {
      const nav = document.querySelector('nav, header, .navbar, .nav-container, [role="navigation"]');
      if (nav && !document.getElementById('notif-bell-btn')) {
        injectBell(nav);
        addAlertsNavTab(tabContent);
        navObserver.disconnect();
      }
    });
    navObserver.observe(document.body, { childList: true, subtree: true });

    // Also try immediately if nav already exists
    const nav = document.querySelector('nav, header, .navbar, .nav-container, [role="navigation"]');
    if (nav && !document.getElementById('notif-bell-btn')) {
      injectBell(nav);
      addAlertsNavTab(tabContent);
      navObserver.disconnect();
    }

    // Show a welcome toast for the first unread notification
    const first = notifications.find(n => !n.read);
    if (first) {
      setTimeout(() => {
        showToast(
          `🔔 ${first.severity}: ${first.ticker} — ${first.title}`,
          first.severity,
          6000
        );
      }, 1500);
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bootstrap);
  } else {
    bootstrap();
  }
})();
