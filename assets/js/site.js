/*
 * site.js - shared by every page: cookie consent, GA4 (consent-gated), waitlist modal.
 * Pure ASCII. Non-ASCII characters must be written as \uXXXX escapes (see CLAUDE.md).
 *
 * OWNER TODO: paste real values below. Both are public identifiers, not secrets.
 */
var GA_MEASUREMENT_ID = 'G-XXXXXXXXXX';          // Google Analytics 4 measurement ID
var WEB3FORMS_ACCESS_KEY = 'YOUR_WEB3FORMS_ACCESS_KEY'; // from https://web3forms.com

(function () {
  'use strict';

  var CONSENT_KEY = 'edm_consent_v1';
  var MIN_FILL_MS = 3000;
  var script = document.currentScript;
  var BASE = script ? script.src.replace(/assets\/js\/site\.js.*$/, '') : '';

  function store(key, val) {
    try {
      if (val === undefined) return JSON.parse(localStorage.getItem(key) || 'null');
      localStorage.setItem(key, JSON.stringify(val));
    } catch (e) { return null; }
  }

  /* ------------------------------------------------------------------
   * Google Consent Mode v2: everything denied by default.
   * gtag.js is only injected after the visitor accepts analytics.
   * ------------------------------------------------------------------ */
  window.dataLayer = window.dataLayer || [];
  window.gtag = function () { window.dataLayer.push(arguments); };
  window.gtag('consent', 'default', {
    ad_storage: 'denied',
    ad_user_data: 'denied',
    ad_personalization: 'denied',
    analytics_storage: 'denied',
    functionality_storage: 'granted',
    security_storage: 'granted',
    wait_for_update: 500
  });

  var gaLoaded = false;
  function gaConfigured() { return /^G-[A-Z0-9]{6,}$/.test(GA_MEASUREMENT_ID) && GA_MEASUREMENT_ID !== 'G-XXXXXXXXXX'; }
  function loadGA() {
    window.gtag('consent', 'update', { analytics_storage: 'granted' });
    if (gaLoaded || !gaConfigured()) return;
    gaLoaded = true;
    var s = document.createElement('script');
    s.async = true;
    s.src = 'https://www.googletagmanager.com/gtag/js?id=' + encodeURIComponent(GA_MEASUREMENT_ID);
    document.head.appendChild(s);
    window.gtag('js', new Date());
    window.gtag('config', GA_MEASUREMENT_ID, { anonymize_ip: true });
  }
  function denyGA() {
    window.gtag('consent', 'update', { analytics_storage: 'denied' });
  }

  function applyConsent(c) {
    if (c && c.analytics) loadGA(); else denyGA();
  }

  /* ---------------- Consent banner ---------------- */
  var banner;
  function buildBanner() {
    banner = document.createElement('section');
    banner.className = 'consent';
    banner.setAttribute('role', 'dialog');
    banner.setAttribute('aria-labelledby', 'consent-title');
    banner.setAttribute('aria-describedby', 'consent-desc');
    banner.innerHTML =
      '<h2 id="consent-title">Cookies &amp; analytics</h2>' +
      '<p id="consent-desc">We use optional Google Analytics cookies to understand how the site is used. ' +
      'Nothing loads unless you accept. <a href="' + BASE + 'privacy.html">Privacy policy</a>.</p>' +
      '<div class="manage" id="consent-manage" hidden>' +
      '  <label><input type="checkbox" checked disabled> <span>Strictly necessary<small>Remembers this choice. Always on.</small></span></label>' +
      '  <label><input type="checkbox" id="consent-analytics"> <span>Analytics (Google Analytics 4)<small>Anonymous usage statistics.</small></span></label>' +
      '</div>' +
      '<div class="row">' +
      '  <button type="button" class="btn btn-cta btn-sm" data-consent="accept">Accept</button>' +
      '  <button type="button" class="btn btn-ghost btn-sm" data-consent="reject">Reject</button>' +
      '  <button type="button" class="btn btn-ghost btn-sm" data-consent="manage" aria-expanded="false" aria-controls="consent-manage">Manage</button>' +
      '  <button type="button" class="btn btn-ghost btn-sm" data-consent="save" hidden>Save choices</button>' +
      '</div>';
    document.body.appendChild(banner);
    banner.addEventListener('click', function (e) {
      var b = e.target.closest('[data-consent]');
      if (!b) return;
      var act = b.getAttribute('data-consent');
      if (act === 'accept') decide(true);
      else if (act === 'reject') decide(false);
      else if (act === 'save') decide(document.getElementById('consent-analytics').checked);
      else if (act === 'manage') {
        var m = document.getElementById('consent-manage');
        var open = m.hasAttribute('hidden');
        if (open) m.removeAttribute('hidden'); else m.setAttribute('hidden', '');
        b.setAttribute('aria-expanded', String(open));
        banner.querySelector('[data-consent="save"]').hidden = !open;
        if (open) document.getElementById('consent-analytics').focus();
      }
    });
  }
  function showBanner() {
    if (!banner) buildBanner();
    var c = store(CONSENT_KEY);
    document.getElementById('consent-analytics').checked = !!(c && c.analytics);
    banner.hidden = false;
  }
  function decide(analytics) {
    var c = { analytics: !!analytics, ts: new Date().toISOString(), v: 1 };
    store(CONSENT_KEY, c);
    applyConsent(c);
    if (banner) banner.hidden = true;
  }
  window.EDM_openCookieSettings = showBanner;

  /* ---------------- Waitlist modal ---------------- */
  var dlg, openedAt = 0, lastTrigger = null;
  function buildDialog() {
    dlg = document.createElement('dialog');
    dlg.className = 'modal';
    dlg.id = 'waitlist';
    dlg.setAttribute('aria-labelledby', 'wl-title');
    dlg.innerHTML =
      '<button type="button" class="modal-close" aria-label="Close" data-close>&times;</button>' +
      '<div class="modal-body">' +
      '  <span class="eyebrow">Early access</span>' +
      '  <h2 id="wl-title">Join the waitlist</h2>' +
      '  <p class="lede">Be first to try live EDGAR crawling and AI filing analysis. One email when it is ready. No spam.</p>' +
      '  <form id="wl-form" novalidate>' +
      '    <div class="field"><label for="wl-name">Name</label>' +
      '      <input id="wl-name" name="name" type="text" autocomplete="name" required maxlength="80" aria-describedby="wl-name-err">' +
      '      <div class="error" id="wl-name-err" aria-live="polite"></div></div>' +
      '    <div class="field"><label for="wl-email">Email</label>' +
      '      <input id="wl-email" name="email" type="email" autocomplete="email" inputmode="email" required maxlength="120" aria-describedby="wl-email-err">' +
      '      <div class="error" id="wl-email-err" aria-live="polite"></div></div>' +
      '    <div class="hp-field" aria-hidden="true">' +
      '      <label for="wl-website">Leave this field empty</label>' +
      '      <input id="wl-website" name="website" type="text" tabindex="-1" autocomplete="off">' +
      '      <input type="checkbox" name="botcheck" id="wl-botcheck" tabindex="-1">' +
      '    </div>' +
      '    <button type="submit" class="btn btn-cta">Get early access</button>' +
      '    <div class="form-status" id="wl-status" role="status" aria-live="polite"></div>' +
      '    <p class="form-note">By joining you agree to our <a href="' + BASE + 'terms.html">Terms</a> and ' +
      '      <a href="' + BASE + 'privacy.html">Privacy Policy</a>. Submissions are delivered via Web3Forms.</p>' +
      '  </form>' +
      '</div>';
    document.body.appendChild(dlg);
    dlg.addEventListener('click', function (e) {
      if (e.target === dlg || e.target.closest('[data-close]')) closeDialog();
    });
    dlg.addEventListener('close', function () { if (lastTrigger) lastTrigger.focus(); });
    var form = dlg.querySelector('#wl-form');
    form.addEventListener('submit', onSubmit);
    ['wl-name', 'wl-email'].forEach(function (id) {
      var el = document.getElementById(id);
      el.addEventListener('blur', function () { if (el.value) validateField(el); });
      el.addEventListener('input', function () { if (el.getAttribute('aria-invalid') === 'true') validateField(el); });
    });
  }
  function openDialog(trigger) {
    if (!dlg) buildDialog();
    lastTrigger = trigger || document.activeElement;
    openedAt = Date.now();
    document.getElementById('wl-status').textContent = '';
    document.getElementById('wl-status').className = 'form-status';
    if (typeof dlg.showModal === 'function') dlg.showModal(); else dlg.setAttribute('open', '');
    setTimeout(function () { document.getElementById('wl-name').focus(); }, 30);
  }
  function closeDialog() {
    if (typeof dlg.close === 'function') dlg.close(); else dlg.removeAttribute('open');
  }
  window.EDM_openWaitlist = openDialog;

  var EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;
  function validateField(el) {
    var msg = '';
    var v = el.value.trim();
    if (el.name === 'name') {
      if (!v) msg = 'Please enter your name.';
      else if (v.length < 2) msg = 'Name looks too short.';
    } else if (el.name === 'email') {
      if (!v) msg = 'Please enter your email address.';
      else if (!EMAIL_RE.test(v)) msg = 'Enter a valid email, like you@example.com.';
    }
    document.getElementById(el.id + '-err').textContent = msg;
    el.setAttribute('aria-invalid', msg ? 'true' : 'false');
    return !msg;
  }

  function setStatus(text, cls) {
    var s = document.getElementById('wl-status');
    s.textContent = text;
    s.className = 'form-status ' + (cls || '');
  }

  function onSubmit(e) {
    e.preventDefault();
    var form = e.target;
    var nameEl = form.querySelector('#wl-name');
    var emailEl = form.querySelector('#wl-email');
    var okName = validateField(nameEl);
    var okEmail = validateField(emailEl);
    if (!okName || !okEmail) { (okName ? emailEl : nameEl).focus(); return; }

    // Spam protection: honeypot + botcheck -> silently "succeed" without sending.
    if (form.querySelector('#wl-website').value || form.querySelector('#wl-botcheck').checked) {
      setStatus('Thanks! You are on the list.', 'ok');
      form.reset();
      return;
    }
    // Spam protection: humans take a few seconds to fill a form.
    if (Date.now() - openedAt < MIN_FILL_MS) {
      setStatus('That was fast. Please wait a moment and try again.', 'err');
      return;
    }
    if (!WEB3FORMS_ACCESS_KEY || WEB3FORMS_ACCESS_KEY.indexOf('YOUR_') === 0) {
      setStatus('Waitlist is not connected yet (owner: add the Web3Forms access key in assets/js/site.js).', 'err');
      return;
    }
    var btn = form.querySelector('button[type="submit"]');
    btn.disabled = true;
    btn.textContent = 'Sending\u2026';
    fetch('https://api.web3forms.com/submit', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      body: JSON.stringify({
        access_key: WEB3FORMS_ACCESS_KEY,
        subject: 'EDGAR Disclosure Monitor - new waitlist signup',
        from_name: 'EDGAR Disclosure Monitor',
        name: nameEl.value.trim(),
        email: emailEl.value.trim(),
        botcheck: false
      })
    }).then(function (r) { return r.json().catch(function () { return {}; }).then(function (j) { return { ok: r.ok, j: j }; }); })
      .then(function (res) {
        if (res.ok && res.j.success !== false) {
          setStatus('Thanks! You are on the list. Watch your inbox.', 'ok');
          form.reset();
        } else {
          setStatus((res.j && res.j.message) || 'Something went wrong. Please try again.', 'err');
        }
      })
      .catch(function () { setStatus('Network error. Check your connection and try again.', 'err'); })
      .then(function () { btn.disabled = false; btn.textContent = 'Get early access'; });
  }

  /* ---------------- Wire up ---------------- */
  document.addEventListener('click', function (e) {
    var t = e.target.closest('[data-waitlist]');
    if (t) { e.preventDefault(); openDialog(t); return; }
    var c = e.target.closest('[data-cookie-settings]');
    if (c) { e.preventDefault(); showBanner(); }
  });

  function init() {
    var c = store(CONSENT_KEY);
    if (c) applyConsent(c); else showBanner();
    if (location.hash === '#waitlist') openDialog();
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
})();
