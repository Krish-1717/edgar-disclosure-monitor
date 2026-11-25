/*
 * landing.js - minimal landing page: a live globe of every SEC-listed company and a
 * search over all of them. Pure ASCII; non-ASCII goes in as \uXXXX (see CLAUDE.md).
 * Data: assets/data/oracle/universe.json (written by `python -m oracle universe`).
 */
(function () {
  'use strict';
  var $ = function (id) { return document.getElementById(id); };
  var reduceMotion = window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches;
  var rows = [];

  function esc(s) { return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;'); }
  function nice(name) {
    var s = String(name || '').replace(/\s*\/[A-Z]{2,3}\/?\s*$/, '').trim();
    if (/[a-z]/.test(s)) return s;
    return s.toLowerCase().replace(/\b([a-z])/g, function (m) { return m.toUpperCase(); }).replace(/\b(Inc|Corp|Co|Ltd)\b/g, '$1.').replace(/\.\./g, '.');
  }
  function openUrl(t) { return 'app.html?t=' + encodeURIComponent(t); }

  /* ---------------- search ---------------- */
  var q = $('hero-q'), list = $('hero-results'), form = $('hero-search'), hits = [], sel = 0;
  function search(text) {
    var Q = text.trim().toUpperCase().replace(/\./g, '-'), U = text.trim().toUpperCase(), out = [], seen = {};
    function add(r) { if (out.length < 7 && !seen[r[0]]) { seen[r[0]] = 1; out.push(r); } }
    if (!Q) return out;
    var i;
    for (i = 0; i < rows.length && out.length < 7; i++) if (rows[i][0] === Q) add(rows[i]);
    for (i = 0; i < rows.length && out.length < 7; i++) if (rows[i][0].indexOf(Q) === 0 && rows[i][0].indexOf('-') < 0) add(rows[i]);
    if (U.length >= 2) {
      for (i = 0; i < rows.length && out.length < 7; i++) if ((' ' + rows[i][1].toUpperCase()).indexOf(' ' + U) >= 0) add(rows[i]);
      for (i = 0; i < rows.length && out.length < 7; i++) if (rows[i][1].toUpperCase().indexOf(U) >= 0) add(rows[i]);
    }
    return out;
  }
  function paintResults() {
    if (!q.value.trim()) { list.hidden = true; return; }
    list.innerHTML = hits.length ? hits.map(function (r, i) {
      return '<li role="option" aria-selected="' + (i === sel) + '"><a href="' + openUrl(r[0]) + '" aria-selected="' + (i === sel) + '"><b>' + esc(r[0]) + '</b><span>' + esc(nice(r[1])) + '</span><small>' + esc(r[3] || '') + '</small></a></li>';
    }).join('') : '<li class="none">' + (rows.length ? 'No SEC-listed company matches.' : 'Loading the list of public companies\u2026') + '</li>';
    list.hidden = false;
  }
  if (q) {
    q.addEventListener('input', function () { hits = search(q.value); sel = 0; paintResults(); });
    q.addEventListener('keydown', function (e) {
      if (e.key === 'ArrowDown' && hits.length) { e.preventDefault(); sel = (sel + 1) % hits.length; paintResults(); }
      else if (e.key === 'ArrowUp' && hits.length) { e.preventDefault(); sel = (sel - 1 + hits.length) % hits.length; paintResults(); }
      else if (e.key === 'Escape') { list.hidden = true; }
    });
    q.addEventListener('blur', function () { setTimeout(function () { list.hidden = true; }, 150); });
    form.addEventListener('submit', function (e) {
      e.preventDefault();
      var t = hits[sel] ? hits[sel][0] : q.value.trim().toUpperCase();
      if (t) location.href = openUrl(t);
    });
  }

  /* ---------------- globe ---------------- */
  var cv = $('globe'), ctx = cv && cv.getContext ? cv.getContext('2d') : null, tip = $('globe-tip');
  var pos = null, sx, sy, dep, ranges = [], N = 0, yaw = 0.6, pitch = -0.32, W = 0, H = 0, DPR = Math.min(2, window.devicePixelRatio || 1);
  var hover = -1, drag = null, moved = false, autoAt = 0, raf = 0;
  var EX_DARK = { NYSE: '150,163,230', Nasdaq: '120,190,210', CBOE: '200,180,140', TXSE: '200,160,190', OTC: '110,116,134' };
  var EX_LIGHT = { NYSE: '66,86,214', Nasdaq: '15,127,148', CBOE: '154,106,12', TXSE: '184,67,126', OTC: '120,126,144' };
  function isLight() {
    var t = document.documentElement.getAttribute('data-theme');
    return t ? t === 'light' : !!(window.matchMedia && matchMedia('(prefers-color-scheme: light)').matches);
  }
  function spiral(n) {
    var out = new Float32Array(n * 3), phi = 0;
    for (var i = 0; i < n; i++) {
      var h = n === 1 ? 0 : -1 + 2 * i / (n - 1), th = Math.acos(h);
      phi = (i === 0 || i === n - 1) ? 0 : (phi + 3.6 / Math.sqrt(n * (1 - h * h))) % (2 * Math.PI);
      out[i * 3] = Math.sin(th) * Math.cos(phi); out[i * 3 + 1] = h; out[i * 3 + 2] = Math.sin(th) * Math.sin(phi);
    }
    return out;
  }
  function build() {
    N = rows.length; pos = spiral(N); sx = new Float32Array(N); sy = new Float32Array(N); dep = new Float32Array(N); ranges = [];
    for (var i = 0; i < N; i++) {
      var ex = rows[i][3] || '';
      if (!ranges.length || ranges[ranges.length - 1].ex !== ex) ranges.push({ ex: ex, a: i, b: i + 1 }); else ranges[ranges.length - 1].b = i + 1;
    }
    var c = $('globe-count'); if (c) c.textContent = N.toLocaleString();
    kick();
  }
  function size() {
    var r = cv.getBoundingClientRect();
    W = r.width; H = r.height;
    cv.width = Math.round(W * DPR); cv.height = Math.round(H * DPR);
  }
  function draw() {
    raf = 0;
    if (!ctx || !N) return;
    if (!W) size();
    ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
    ctx.clearRect(0, 0, W, H);
    var R = Math.min(W, H) * 0.44, cx = W / 2, cy = H / 2, cyw = Math.cos(yaw), syw = Math.sin(yaw), cp = Math.cos(pitch), sp = Math.sin(pitch), F = 4.2;
    for (var i = 0; i < N; i++) {
      var x = pos[i * 3], y = pos[i * 3 + 1], z = pos[i * 3 + 2];
      var x1 = x * cyw + z * syw, z1 = -x * syw + z * cyw, y2 = y * cp - z1 * sp, z2 = y * sp + z1 * cp, s = F / (F - z2);
      sx[i] = cx + x1 * R * s; sy[i] = cy + y2 * R * s; dep[i] = (z2 + 1) / 2;
    }
    var light = isLight(), pal = light ? EX_LIGHT : EX_DARK;
    ranges.forEach(function (r) {
      for (var band = 0; band < 4; band++) {
        var a = (light ? 0.12 : 0.08) + (light ? 0.62 : 0.6) * (band + 0.5) / 4, rad = 0.6 + 0.8 * (band + 0.5) / 4;
        ctx.fillStyle = 'rgba(' + (pal[r.ex] || pal.OTC) + ',' + a.toFixed(3) + ')';
        for (var j = r.a; j < r.b; j++) {
          var d = dep[j];
          if ((d >= 1 ? 3 : Math.floor(d * 4)) !== band) continue;
          ctx.fillRect(sx[j] - rad, sy[j] - rad, rad * 2, rad * 2);
        }
      }
    });
    if (hover >= 0) {
      ctx.strokeStyle = light ? 'rgba(20,22,27,0.9)' : 'rgba(238,241,255,0.95)'; ctx.lineWidth = 1.5;
      ctx.beginPath(); ctx.arc(sx[hover], sy[hover], 6, 0, Math.PI * 2); ctx.stroke();
    }
    if (!reduceMotion && !drag && Date.now() > autoAt) { yaw += 0.0018; pitch = -0.32 + Math.sin(Date.now() / 7000) * 0.25; kick(); }
  }
  function kick() { if (!raf && !document.hidden) raf = requestAnimationFrame(draw); }
  function pick(e) {
    var r = cv.getBoundingClientRect(), x = e.clientX - r.left, y = e.clientY - r.top, best = -1, bd = 49;
    for (var i = 0; i < N; i++) {
      if (dep[i] < 0.5) continue;
      var dx = sx[i] - x, dy = sy[i] - y, dd = dx * dx + dy * dy;
      if (dd < bd) { bd = dd; best = i; }
    }
    return best;
  }
  if (ctx) {
    fetch('assets/data/oracle/universe.json').then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then(function (u) { rows = u.companies || []; build(); if (q && q.value) { hits = search(q.value); paintResults(); } })
      .catch(function () { var c = document.querySelector('.hero-globe figcaption'); if (c) c.textContent = 'The company list could not load. Search still opens the app.'; });
    if (window.ResizeObserver) new ResizeObserver(function () { W = 0; kick(); }).observe(cv);
    document.addEventListener('visibilitychange', kick);
    window.addEventListener('edm-theme', kick);
    cv.addEventListener('pointerdown', function (e) { drag = { x: e.clientX, y: e.clientY, id: e.pointerId }; moved = false; try { cv.setPointerCapture(e.pointerId); } catch (err) {} });
    cv.addEventListener('pointermove', function (e) {
      if (drag && e.pointerId === drag.id) {
        var dx = e.clientX - drag.x, dy = e.clientY - drag.y;
        if (Math.abs(dx) + Math.abs(dy) > 3) moved = true;
        drag.x = e.clientX; drag.y = e.clientY;
        if (moved) { yaw += dx * 0.006; pitch = Math.max(-1.3, Math.min(1.3, pitch + dy * 0.006)); cv.classList.add('dragging'); tip.hidden = true; autoAt = Date.now() + 6000; kick(); }
        return;
      }
      var k = pick(e);
      if (k !== hover) { hover = k; kick(); }
      cv.classList.toggle('over', k >= 0);
      if (k >= 0) {
        var r = cv.getBoundingClientRect(), u = rows[k];
        tip.innerHTML = '<b>' + esc(u[0]) + '</b> \u00b7 ' + esc(nice(u[1])) + '<br>' + esc(u[3] || 'Unlisted') + ' \u00b7 click to open';
        tip.hidden = false;
        tip.style.left = Math.max(0, Math.min(r.width - 220, e.clientX - r.left + 12)) + 'px';
        tip.style.top = (e.clientY - r.top - 8) + 'px';
      } else tip.hidden = true;
    });
    cv.addEventListener('pointerup', function (e) {
      if (!drag) return;
      cv.classList.remove('dragging');
      var wasClick = !moved; drag = null;
      if (wasClick) { var k = pick(e); if (k >= 0) location.href = openUrl(rows[k][0]); }
    });
    cv.addEventListener('pointerleave', function () { if (!drag) { hover = -1; tip.hidden = true; kick(); } });
    kick();
  }
})();
